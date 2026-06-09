# Project Accenture

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
