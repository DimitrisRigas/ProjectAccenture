"""
src/jobs/test_vector_search.py

Test semantic search against the Databricks Vector Search index.
"""

from databricks.vector_search.client import VectorSearchClient


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

INDEX_NAME = f"{CATALOG}.{SCHEMA}.gold_document_embeddings_index"
VECTOR_SEARCH_ENDPOINT_NAME = "regulatory_compliance_vector_search_endpoint"


def main():
    client = VectorSearchClient(disable_notice=True)

    index = client.get_index(
        endpoint_name=VECTOR_SEARCH_ENDPOINT_NAME,
        index_name=INDEX_NAME,
    )

    query = "What are the obligations for personal data protection under GDPR?"

    results = index.similarity_search(
        query_text=query,
        columns=[
            "chunk_id",
            "short_title",
            "regulation_title",
            "source_url",
            "page_number",
            "section_number",
            "chunk_text",
        ],
        num_results=5,
    )

    print("Query:")
    print(query)
    print("=" * 100)

    rows = results["result"]["data_array"]

    for row in rows:
        print(row)
        print("-" * 100)


if __name__ == "__main__":
    main()