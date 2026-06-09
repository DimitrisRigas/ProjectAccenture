"""
src/jobs/create_vector_index.py

Create a Databricks Vector Search endpoint and Delta Sync index.

The index uses Databricks-managed embeddings:
    source text column: chunk_text
    primary key: chunk_id

Source table:
    accenture2026dbcks.team4.gold_document_embeddings

Index:
    accenture2026dbcks.team4.gold_document_embeddings_index
"""

import time

from databricks.vector_search.client import VectorSearchClient


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.gold_document_embeddings"
INDEX_NAME = f"{CATALOG}.{SCHEMA}.gold_document_embeddings_index"

VECTOR_SEARCH_ENDPOINT_NAME = "regulatory_compliance_vector_search_endpoint"

EMBEDDING_MODEL_ENDPOINT = "databricks-qwen3-embedding-0-6b"

MAX_SYNC_ATTEMPTS = 15
WAIT_SECONDS = 60


def sync_index_with_retry(index):
    """
    Databricks Vector Search indexes can take a few minutes to become ready.
    If we call sync too early, Databricks returns:
        Vector index ... is not ready.

    This function retries until the index accepts the sync request.
    """

    for attempt in range(1, MAX_SYNC_ATTEMPTS + 1):
        try:
            print(f"Sync attempt {attempt}/{MAX_SYNC_ATTEMPTS}")
            index.sync()
            print("Vector Search index sync started successfully.")
            return

        except Exception as error:
            error_message = str(error)

            if "not ready" in error_message.lower():
                print("Index is not ready yet.")
                print(f"Waiting {WAIT_SECONDS} seconds before retrying...")
                time.sleep(WAIT_SECONDS)
                continue

            raise

    raise RuntimeError(
        f"Index was still not ready after "
        f"{MAX_SYNC_ATTEMPTS * WAIT_SECONDS} seconds."
    )


def main():
    client = VectorSearchClient(disable_notice=True)

    print(f"Creating/checking Vector Search endpoint: {VECTOR_SEARCH_ENDPOINT_NAME}")

    try:
        client.create_endpoint(
            name=VECTOR_SEARCH_ENDPOINT_NAME,
            endpoint_type="STANDARD",
        )
        print("Vector Search endpoint creation requested.")

    except Exception as error:
        print("Endpoint may already exist, continuing.")
        print(f"Details: {error}")

    print(f"Creating/checking Vector Search index: {INDEX_NAME}")

    try:
        index = client.create_delta_sync_index(
            endpoint_name=VECTOR_SEARCH_ENDPOINT_NAME,
            source_table_name=SOURCE_TABLE,
            index_name=INDEX_NAME,
            pipeline_type="TRIGGERED",
            primary_key="chunk_id",
            embedding_source_column="chunk_text",
            embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
            columns_to_sync=[
                "chunk_id",
                "document_id",
                "celex",
                "short_title",
                "regulation_title",
                "regulation_category",
                "compliance_domain",
                "document_type",
                "language",
                "source_system",
                "source_url",
                "file_format",
                "file_name",
                "page_number",
                "section_number",
                "chunk_index",
                "chunk_length",
                "chunk_text",
            ],
        )

        print("Vector Search index creation requested.")

    except Exception as error:
        print("Index may already exist, trying to fetch it.")
        print(f"Details: {error}")

        index = client.get_index(
            endpoint_name=VECTOR_SEARCH_ENDPOINT_NAME,
            index_name=INDEX_NAME,
        )

    print("Index description:")
    print(index.describe())

    print("Starting index sync with retry...")
    sync_index_with_retry(index)


if __name__ == "__main__":
    main()