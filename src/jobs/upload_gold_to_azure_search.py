"""
src/jobs/upload_gold_to_azure_search.py

Read the Databricks Gold table (which ALREADY contains embeddings) and
upload chunks to Azure AI Search.

Embeddings are NOT computed here — they are read directly from the Gold
table's `embedding` column (produced by gold_embeddings.py). This avoids
re-embedding on every index rebuild.

Input:
    accenture2026dbcks.team4.gold_chunk_embeddings

Expected Databricks secrets (scope: compliance-assistant):
    - AI_SEARCH_ENDPOINT
    - AI_SEARCH_API_KEY
"""

from __future__ import annotations

import os
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# =============================================================================
# Secret helpers
# =============================================================================

def get_databricks_secret(scope: str, key: str) -> str | None:
    try:
        from databricks.sdk.runtime import dbutils
        return dbutils.secrets.get(scope=scope, key=key)
    except Exception as error:
        print(f"Could not read secret: scope={scope}, key={key}")
        print(f"Secret read error: {type(error).__name__}: {error}")
        return None


def get_secret_or_env(env_name, secret_scope, secret_key, default=None):
    value = os.getenv(env_name)
    if value:
        return value
    secret_value = get_databricks_secret(scope=secret_scope, key=secret_key)
    if secret_value:
        return secret_value
    return default


# =============================================================================
# Configuration
# =============================================================================

SECRET_SCOPE = os.getenv("SECRET_SCOPE", "compliance-assistant")

CATALOG = os.getenv("DATABRICKS_CATALOG", "accenture2026dbcks")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "team4")

GOLD_EMBEDDINGS_TABLE = os.getenv(
    "GOLD_EMBEDDINGS_TABLE",
    f"{CATALOG}.{SCHEMA}.gold_chunk_embeddings",
)

AI_SEARCH_ENDPOINT = get_secret_or_env(
    env_name="AI_SEARCH_ENDPOINT",
    secret_scope=SECRET_SCOPE,
    secret_key="AI_SEARCH_ENDPOINT",
)

AI_SEARCH_API_KEY = get_secret_or_env(
    env_name="AI_SEARCH_API_KEY",
    secret_scope=SECRET_SCOPE,
    secret_key="AI_SEARCH_API_KEY",
)

AI_SEARCH_INDEX_NAME = os.getenv("AI_SEARCH_INDEX_NAME", "team4")

UPLOAD_BATCH_SIZE = int(os.getenv("UPLOAD_BATCH_SIZE", "100"))


# =============================================================================
# Validation
# =============================================================================

def validate_environment() -> None:
    required = {
        "AI_SEARCH_ENDPOINT or secret AI_SEARCH_ENDPOINT": AI_SEARCH_ENDPOINT,
        "AI_SEARCH_API_KEY or secret AI_SEARCH_API_KEY": AI_SEARCH_API_KEY,
        "AI_SEARCH_INDEX_NAME": AI_SEARCH_INDEX_NAME,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            "Missing required configuration:\n"
            + "\n".join(f"- {name}" for name in missing)
        )


# =============================================================================
# Client
# =============================================================================

def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AI_SEARCH_API_KEY),
    )


# =============================================================================
# Build documents from Gold rows (embeddings already present)
# =============================================================================

def build_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents = []
    for item in rows:
        page_number = item.get("page_number")
        if page_number is not None:
            page_number = int(page_number)
        documents.append(
            {
                "chunk_id": str(item["chunk_id"]),
                "chunk_text": item["chunk_text"],
                "embedding": item["embedding"],
                "short_title": item.get("short_title"),
                "regulation_title": item.get("regulation_title"),
                "source_url": item.get("source_url"),
                "page_number": page_number,
                "file_name": item.get("file_name"),
            }
        )
    return documents


# =============================================================================
# Upload
# =============================================================================

def upload_documents(search_client, documents):
    total = len(documents)
    for start in range(0, total, UPLOAD_BATCH_SIZE):
        end = start + UPLOAD_BATCH_SIZE
        batch = documents[start:end]
        print(f"Uploading documents {start + 1}-{min(end, total)} of {total}")
        results = search_client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        if failed:
            raise RuntimeError(f"Some documents failed to upload: {failed}")
    print("Upload to Azure AI Search completed.")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    validate_environment()

    spark = SparkSession.builder.getOrCreate()

    print("=" * 100)
    print("Uploading Gold chunks (with embeddings) to Azure AI Search")
    print(f"Gold table: {GOLD_EMBEDDINGS_TABLE}")
    print(f"Index: {AI_SEARCH_INDEX_NAME}")
    print("=" * 100)

    gold_df = (
        spark.table(GOLD_EMBEDDINGS_TABLE)
        .select(
            "chunk_id",
            "chunk_text",
            "embedding",
            "short_title",
            "regulation_title",
            "source_url",
            "page_number",
            "file_name",
        )
        .filter(F.col("chunk_id").isNotNull())
        .filter(F.col("chunk_text").isNotNull())
        .filter(F.length(F.trim(F.col("chunk_text"))) > 0)
        .filter(F.col("embedding").isNotNull())
        .dropDuplicates(["chunk_id"])
    )

    total_rows = gold_df.count()
    print(f"Rows to upload: {total_rows}")
    if total_rows == 0:
        raise ValueError("Gold table has no rows to upload.")

    rows = [row.asDict(recursive=True) for row in gold_df.collect()]

    search_client = get_search_client()
    documents = build_documents(rows)
    upload_documents(search_client, documents)

    print("=" * 100)
    print(f"Done. Uploaded documents: {len(documents)}")
    print("=" * 100)


if __name__ == "__main__":
    main()