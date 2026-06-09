"""
src/jobs/create_azure_search_index.py

Create or update an Azure AI Search vector index for regulatory RAG.

This script is intended to run inside Databricks as part of the job pipeline.

Expected Databricks secrets:
    Scope:
        azure-rag

    Keys:
        ai-search-endpoint
        ai-search-api-key

Index fields:
    - chunk_id
    - chunk_text
    - embedding
    - short_title
    - regulation_title
    - source_url
    - page_number
    - file_name
"""

from __future__ import annotations

import os
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)


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

EMBEDDING_DIMENSIONS = int(
    os.getenv(
        "EMBEDDING_DIMENSIONS",
        "1536",
    )
)


# =============================================================================
# Validation
# =============================================================================

def validate_environment() -> None:
    missing = []

    if not AI_SEARCH_ENDPOINT:
        missing.append("AI_SEARCH_ENDPOINT or Databricks secret ai-search-endpoint")

    if not AI_SEARCH_API_KEY:
        missing.append("AI_SEARCH_API_KEY or Databricks secret ai-search-api-key")

    if not AI_SEARCH_INDEX_NAME:
        missing.append("AI_SEARCH_INDEX_NAME")

    if missing:
        raise ValueError(
            "Missing required configuration:\n"
            + "\n".join(f"- {name}" for name in missing)
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    validate_environment()

    print("=" * 100)
    print("Creating or updating Azure AI Search index")
    print("=" * 100)
    print(f"Secret scope: {SECRET_SCOPE}")
    print(f"Search endpoint: {AI_SEARCH_ENDPOINT}")
    print(f"Index name: {AI_SEARCH_INDEX_NAME}")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")
    print("=" * 100)

    client = SearchIndexClient(
        endpoint=AI_SEARCH_ENDPOINT,
        credential=AzureKeyCredential(AI_SEARCH_API_KEY),
    )

    fields = [
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
            sortable=True,
        ),
        SearchableField(
            name="chunk_text",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="vector-profile",
        ),
        SimpleField(
            name="short_title",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SearchableField(
            name="regulation_title",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
        ),
        SimpleField(
            name="source_url",
            type=SearchFieldDataType.String,
        ),
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="file_name",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    index = SearchIndex(
        name=AI_SEARCH_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )

    client.create_or_update_index(index)

    print("=" * 100)
    print(f"Azure AI Search index created/updated: {AI_SEARCH_INDEX_NAME}")
    print("=" * 100)


if __name__ == "__main__":
    main()