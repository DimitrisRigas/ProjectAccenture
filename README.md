# Project Accenture

We implemented the full end-to-end RAG pipeline: regulatory ingestion, Databricks Bronze/Silver/Gold processing, Azure OpenAI embeddings, Azure AI Search indexing, FastAPI API, and frontend answer generation with source traceability.

For governance, we added Databricks Secrets, source metadata, document provenance, and lightweight PII redaction.

For evaluation, we created a small benchmark dataset and an automated script that checks source retrieval, expected regulation matching, and answer quality indicators.

For DevOps, we used Databricks Bundles for workflow orchestration and added Docker/GitHub Actions for local API validation.

## Gold embeddings
### How to run:
Push the secrets to Databricks (run once, locally)
1. Create the scope `databricks secrets create-scope compliance-assistant`
2. If that errors saying it exists, fine. Verify: `databricks secrets list-scopes`
3. Now push each secret:
   1. databricks secrets put-secret compliance-assistant AZURE_OPENAI_API_KEY --string-value "<value>"
   2. databricks secrets put-secret compliance-assistant AZURE_OPENAI_ENDPOINT --string-value "<value>"
   3. databricks secrets put-secret compliance-assistant AZURE_OPENAI_API_VERSION --string-value "<value>"
   4. databricks secrets put-secret compliance-assistant EMBEDDING_MODEL_NAME --string-value "text-embedding-3-small"
4. Verify they landed: `databricks secrets list-secrets compliance-assistant`
