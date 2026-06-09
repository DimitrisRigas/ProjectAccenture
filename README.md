We implemented the full end-to-end RAG pipeline: regulatory ingestion, Databricks Bronze/Silver/Gold processing, Azure OpenAI embeddings, Azure AI Search indexing, FastAPI API, and frontend answer generation with source traceability.

For governance, we added Databricks Secrets, source metadata, document provenance, and lightweight PII redaction.

For evaluation, we created a small benchmark dataset and an automated script that checks source retrieval, expected regulation matching, and answer quality indicators.

For DevOps, we used Databricks Bundles for workflow orchestration and added Docker/GitHub Actions for local API validation.