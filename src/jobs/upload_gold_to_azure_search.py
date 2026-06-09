"""
src/jobs/upload_gold_to_azure_search.py

Read the Databricks Gold table and upload chunks to Azure AI Search.

This script is intended to run inside Databricks as part of the job pipeline.

Input:
    accenture2026dbcks.team4.gold_document_embeddings

Output:
    Azure AI Search index documents with:
        - chunk_id
        - chunk_text
        - embedding
        - short_title
        - regulation_title
        - source_url
        - page_number
        - file_name

Expected Databricks secrets:
    Scope:
        azure-rag

    Keys:
        ai-search-endpoint
        ai-search-api-key
        azure-openai-endpoint
        azure-openai-api-key
"""

from __future__ import annotations

import os
from typing import Any, Optional

from openai import AzureOpenAI

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# =============================================================================
# Secret helper
# =============================================================================

def get_databricks_secret(
    scope: str,
    key: str,
) -> str | None:
    """
    Read a secret from Databricks.

    Works in Databricks jobs using databricks.sdk.runtime.dbutils.
    """

    try:
        from databricks.sdk.runtime import dbutils

        return dbutils.secrets.get(
            scope=scope,
            key=key,
        )

    except Exception as error:
        print(f"Could not read secret: scope={scope}, key={key}")
        print(f"Secret read error: {type(error).__name__}: {error}")
        return None


def get_secret_or_env(
    env_name: str,
    secret_scope: str,
    secret_key: str,
    default: str | None = None,
) -> str | None:
    """
    First try environment variable.
    If missing, try Databricks secret.
    If still missing, use default.
    """

    value = os.getenv(env_name)

    if value:
        return value

    secret_value = get_databricks_secret(
        scope=secret_scope,
        key=secret_key,
    )

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
    f"{CATALOG}.{SCHEMA}.gold_document_embeddings",
)

AZURE_OPENAI_ENDPOINT = get_secret_or_env(
    env_name="AZURE_OPENAI_ENDPOINT",
    secret_scope=SECRET_SCOPE,
    secret_key="AZURE_OPENAI_ENDPOINT",
)

AZURE_OPENAI_API_KEY = get_secret_or_env(
    env_name="AZURE_OPENAI_API_KEY",
    secret_scope=SECRET_SCOPE,
    secret_key="AZURE_OPENAI_API_KEY",
)

AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION",
    "2024-02-01",
)

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "text-embedding-3-small",
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
AI_SEARCH_INDEX_NAME = os.getenv(
    "AI_SEARCH_INDEX_NAME",
    "team4",
)

EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
UPLOAD_BATCH_SIZE = int(os.getenv("UPLOAD_BATCH_SIZE", "100"))


# =============================================================================
# Validation
# =============================================================================

def validate_environment() -> None:
    required = {
        "AZURE_OPENAI_ENDPOINT or secret azure-openai-endpoint": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY or secret azure-openai-api-key": AZURE_OPENAI_API_KEY,
        "EMBEDDING_MODEL_NAME": EMBEDDING_MODEL_NAME,
        "AI_SEARCH_ENDPOINT or secret ai-search-endpoint": AI_SEARCH_ENDPOINT,
        "AI_SEARCH_API_KEY or secret ai-search-api-key": AI_SEARCH_API_KEY,
        "AI_SEARCH_INDEX_NAME": AI_SEARCH_INDEX_NAME,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing required configuration:\n"
            + "\n".join(f"- {name}" for name in missing)
        )


# =============================================================================
# Clients
# =============================================================================

def get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AI_SEARCH_API_KEY),
    )


# =============================================================================
# Embeddings
# =============================================================================

def embed_texts(
    openai_client: AzureOpenAI,
    texts: list[str],
) -> list[list[float]]:
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL_NAME,
        input=texts,
    )

    return [
        item.embedding
        for item in response.data
    ]


def add_embeddings(
    openai_client: AzureOpenAI,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents = []
    total = len(rows)

    for start in range(0, total, EMBEDDING_BATCH_SIZE):
        end = start + EMBEDDING_BATCH_SIZE
        batch = rows[start:end]

        print(f"Embedding rows {start + 1}-{min(end, total)} of {total}")

        texts = [
            item["chunk_text"]
            for item in batch
        ]

        embeddings = embed_texts(
            openai_client=openai_client,
            texts=texts,
        )

        for item, embedding in zip(batch, embeddings):
            page_number = item.get("page_number")

            if page_number is not None:
                page_number = int(page_number)

            documents.append(
                {
                    "chunk_id": item["chunk_id"],
                    "chunk_text": item["chunk_text"],
                    "embedding": embedding,
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

def upload_documents(
    search_client: SearchClient,
    documents: list[dict[str, Any]],
) -> None:
    total = len(documents)

    for start in range(0, total, UPLOAD_BATCH_SIZE):
        end = start + UPLOAD_BATCH_SIZE
        batch = documents[start:end]

        print(f"Uploading documents {start + 1}-{min(end, total)} of {total}")

        results = search_client.upload_documents(
            documents=batch,
        )

        failed = [
            result
            for result in results
            if not result.succeeded
        ]

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
    print("Uploading Databricks Gold chunks to Azure AI Search")
    print("=" * 100)
    print(f"Secret scope: {SECRET_SCOPE}")
    print(f"Gold table: {GOLD_EMBEDDINGS_TABLE}")
    print(f"Azure AI Search endpoint: {AI_SEARCH_ENDPOINT}")
    print(f"Azure AI Search index: {AI_SEARCH_INDEX_NAME}")
    print(f"Azure OpenAI API version: {AZURE_OPENAI_API_VERSION}")
    print(f"Embedding model/deployment: {EMBEDDING_MODEL_NAME}")
    print(f"Embedding batch size: {EMBEDDING_BATCH_SIZE}")
    print(f"Upload batch size: {UPLOAD_BATCH_SIZE}")
    print("=" * 100)

    gold_df = (
        spark.table(GOLD_EMBEDDINGS_TABLE)
        .select(
            "chunk_id",
            "chunk_text",
            "short_title",
            "regulation_title",
            "source_url",
            "page_number",
            "file_name",
        )
        .filter(F.col("chunk_id").isNotNull())
        .filter(F.col("chunk_text").isNotNull())
        .filter(F.length(F.trim(F.col("chunk_text"))) > 0)
        .dropDuplicates(["chunk_id"])
    )

    total_rows = gold_df.count()
    print(f"Rows to upload: {total_rows}")

    if total_rows == 0:
        raise ValueError("Gold table has no rows to upload.")

    rows = [
        row.asDict(recursive=True)
        for row in gold_df.collect()
    ]

    openai_client = get_openai_client()
    search_client = get_search_client()

    documents = add_embeddings(
        openai_client=openai_client,
        rows=rows,
    )

    upload_documents(
        search_client=search_client,
        documents=documents,
    )

    print("=" * 100)
    print("Done.")
    print(f"Uploaded documents: {len(documents)}")
    print("=" * 100)


if __name__ == "__main__":
    main()