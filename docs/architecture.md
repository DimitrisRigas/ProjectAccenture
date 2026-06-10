# System Architecture

## 1. Overview

The AI-Powered Regulatory Compliance Assistant is an end-to-end Retrieval-Augmented Generation system for EU financial regulatory documents.

The system ingests regulatory documents, processes them into AI-ready chunks, generates embeddings in the Gold layer, uploads the embedded chunks to Azure AI Search, and exposes a FastAPI and frontend interface for natural-language question answering.

The architecture combines:

* Databricks for governed data engineering,
* Delta Lake for Bronze/Silver/Gold processing,
* Azure OpenAI for embedding generation and answer generation,
* Azure AI Search for vector and hybrid retrieval,
* FastAPI for the API layer,
* Docker for the local application layer,
* and a browser frontend for user interaction.

---

## 2. High-Level Architecture

```text
Regulatory Sources (EUR-Lex via CELEX IDs)
    ↓
Databricks Bronze Ingestion (downloads directly)
    ↓
Bronze Delta Tables
    ↓
Silver Chunking
    ↓
Gold Embedding Generation
    ↓
Azure AI Search Index Upload
    ↓
Hybrid Retrieval
    ↓
GPT-4o Answer Generation
    ↓
FastAPI Backend
    ↓
Frontend Application
```

---

## 3. Architecture Layers

| Layer                  | Purpose                                     | Implementation                                 |
| ---------------------- | ------------------------------------------- | ---------------------------------------------- |
| Data Sources Layer     | Collect regulatory documents                | EUR-Lex, EBA, ECB sources                      |
| Ingestion Layer        | Download and ingest regulatory documents    | `src/jobs/bronze_ingestion.py` (downloads from EUR-Lex) |
| Data Engineering Layer | Transform raw data into AI-ready tables     | Databricks, PySpark, Delta Lake                |
| Gold AI Layer          | Generate and store embeddings               | `src/jobs/gold_embeddings.py`, Azure OpenAI    |
| Retrieval Layer        | Retrieve relevant regulatory chunks         | Azure AI Search                                |
| RAG Layer              | Build context and generate grounded answers | `src/rag_service.py`                           |
| API Layer              | Expose question-answering endpoint          | FastAPI `/ask`                                 |
| Application Layer      | User interface                              | HTML/CSS/JavaScript frontend                   |
| Governance Layer       | Secrets, PII, traceability                  | Databricks Secrets, PII redaction, metadata    |
| DevOps Layer           | Local application containerization          | Dockerfile, Docker Compose                     |
| Evaluation Layer       | Measure retrieval and answer quality        | `src/evaluation/evaluate_rag.py`               |

---

## 4. Data Sources

The system uses publicly available EU regulatory and compliance documents, including:

* GDPR
* DORA
* PSD2
* MiFID II
* EU AI Act
* EBA HTML regulatory guidance
* ECB XML source data

The dataset contains PDF, HTML, and XML files. The documents are represented in a metadata manifest that tracks file format, source URL, regulation title, short title, document ID, and ingestion status.

---

## 5. Ingestion Layer

The ingestion layer is fully handled within Databricks by:

```text
src/jobs/bronze_ingestion.py
```

The Bronze ingestion job downloads regulatory documents directly from EUR-Lex using CELEX IDs. It then extracts text from the downloaded PDF, HTML, and XML files and writes the results to Bronze Delta tables. There is no local download or manual upload step.

---

## 6. Databricks Data Engineering Layer

The Databricks processing pipeline follows the Medallion Architecture.

### Bronze Layer

The Bronze layer stores raw extracted document content and metadata.

Main job:

```text
src/jobs/bronze_ingestion.py
```

Outputs:

```text
accenture2026dbcks.team4.bronze_regulatory_documents
accenture2026dbcks.team4.bronze_document_pages
```

The Bronze job extracts text from:

* PDF documents,
* HTML pages,
* XML files.

It preserves source metadata and page-level lineage.

### Silver Layer

The Silver layer creates AI-ready chunks.

Main job:

```text
src/jobs/silver_chunking.py
```

Output:

```text
accenture2026dbcks.team4.silver_document_chunks
```

The Silver job splits long regulatory text into overlapping chunks and keeps metadata such as:

* document ID,
* CELEX ID,
* regulation title,
* short title,
* page number,
* source URL,
* file name,
* chunk index,
* chunk length.

### Gold Embedding Layer

The Gold layer creates the final AI-ready embeddings table.

Main job:

```text
src/jobs/gold_embeddings.py
```

Input:

```text
accenture2026dbcks.team4.silver_document_chunks
```

Output:

```text
accenture2026dbcks.team4.gold_chunk_embeddings
```

The Gold job reads regulatory chunks from the Silver table and generates embeddings using Azure OpenAI. The resulting Gold table contains both the original chunk text and the generated embedding vector.

The Gold table includes:

* chunk ID,
* chunk text,
* regulation title,
* short title,
* source URL,
* page number,
* file name,
* metadata fields,
* and embedding vector.

This makes the Gold table the final AI-ready retrieval dataset.

---

## 7. Azure AI Search Index and Upload Layer

The Azure AI Search index is created by:

```text
src/jobs/create_azure_search_index.py
```

The index contains the following fields:

* `chunk_id`
* `chunk_text`
* `embedding`
* `short_title`
* `regulation_title`
* `source_url`
* `page_number`
* `file_name`

The embedding field uses 1536 dimensions, matching the Azure OpenAI `text-embedding-3-small` embedding model.

The upload job is:

```text
src/jobs/upload_gold_to_azure_search.py
```

This job reads the existing embeddings from the Gold table:

```text
accenture2026dbcks.team4.gold_chunk_embeddings
```

The upload job does not call Azure OpenAI and does not compute embeddings. It uploads the existing chunk text, metadata, and embedding vectors to Azure AI Search.

This design avoids duplicate embedding generation and makes the indexing stage faster and cheaper.

The upload job sends the following fields to Azure AI Search:

* `chunk_id`
* `chunk_text`
* `embedding`
* `short_title`
* `regulation_title`
* `source_url`
* `page_number`
* `file_name`

---

## 8. Retrieval and RAG Layer

The RAG logic is implemented in:

```text
src/rag_service.py
```

The RAG service performs:

1. Environment validation.
2. Question embedding using Azure OpenAI.
3. Hybrid retrieval using Azure AI Search.
4. Context construction from retrieved chunks.
5. GPT-4o answer generation.
6. Source formatting for the frontend.

Hybrid retrieval combines:

* keyword search using the original user question,
* vector search using the question embedding.

This improves retrieval quality because exact regulatory terms such as GDPR, DORA, PSD2, MiFID II, and AI Act are considered alongside semantic similarity.

---

## 9. Prompting Strategy

The system prompt is designed for compliance use cases.

It instructs the model to:

* answer only from retrieved context,
* avoid hallucinated legal claims,
* cite sources using source labels,
* distinguish obligations from general context,
* use professional compliance language,
* mention uncertainty when the context is insufficient,
* and avoid unsupported legal interpretations.

The answer generation temperature is set to `0.0` to make responses more deterministic and less creative.

---

## 10. API Layer

The API layer is implemented with FastAPI:

```text
src/frontend/api.py
```

Main endpoint:

```text
POST /ask
```

The endpoint accepts:

```json
{
  "question": "According to GDPR, what obligations do controllers have?",
  "top_k": 5
}
```

The response includes:

```json
{
  "question": "...",
  "answer": "...",
  "sources": [...]
}
```

The API also includes:

* request validation,
* CORS configuration,
* API key authentication,
* PII redaction,
* error handling,
* and Swagger/OpenAPI documentation.

---

## 11. Frontend Layer

The frontend is implemented as:

```text
src/frontend/index.html
```

It provides:

* a user question input,
* example regulatory questions,
* answer display,
* retrieved source cards,
* source metadata,
* page numbers,
* source URLs,
* retrieval scores,
* and chunk previews.

The frontend calls the FastAPI `/ask` endpoint and displays the answer with traceability.

---

## 12. Dockerized Local Application Layer

The local application layer is Dockerized using Docker and Docker Compose.

Docker files:

```text
Dockerfile
docker-compose.yml
.dockerignore
```

The Docker container runs:

* FastAPI backend,
* RAG service,
* Azure AI Search retrieval client,
* Azure OpenAI client,
* API key authentication,
* and PII redaction logic.

Databricks, Azure OpenAI, Azure AI Search, Unity Catalog, and Delta tables remain external managed cloud services.

Runtime configuration is injected through the `.env` file using Docker Compose. The `.env` file is not copied into the Docker image and should not be committed to Git.

---

## 13. Governance and Security

The architecture includes several governance and security controls:

* local secrets stored in `.env`,
* `.env` excluded from Git,
* Databricks secrets for cloud job credentials,
* API key authentication for the `/ask` endpoint,
* PII redaction before RAG execution,
* source traceability through metadata,
* grounded prompt rules,
* and LLM-as-judge groundedness evaluation.

The current API key mechanism is suitable for demonstration. In a production system, it should be replaced with OAuth2, JWT, Azure AD, or another enterprise authentication mechanism.

---

## 14. Databricks Secrets

Databricks jobs read cloud credentials from the secret scope:

```text
compliance-assistant
```

Required keys:

```text
AI_SEARCH_ENDPOINT
AI_SEARCH_API_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
AZURE_OPENAI_API_VERSION
EMBEDDING_MODEL_NAME
```

The Gold embeddings job uses the Azure OpenAI secrets to generate embeddings. The Azure AI Search upload job uses the AI Search secrets to upload embedded chunks to the search index.

---

## 15. Evaluation and Monitoring

The evaluation pipeline is implemented in:

```text
src/evaluation/evaluate_rag.py
```

It uses:

```text
evaluation/evaluation_questions.json
evaluation/evaluation_results.json
docs/evaluation_report.md
```

The evaluation checks:

* source availability,
* expected regulation match,
* top source correctness,
* keyword coverage,
* average retrieval score,
* faithfulness score,
* groundedness pass rate,
* and unsupported claims.

The final benchmark contains 12 questions and achieved:

| Metric                     |    Result |
| -------------------------- | --------: |
| Total questions            |        12 |
| Passed questions           |        12 |
| Pass rate                  |      100% |
| Average keyword coverage   |     95.8% |
| Average faithfulness score | 4.917 / 5 |
| Groundedness pass count    |   12 / 12 |

---

## 16. Databricks Workflow

The Databricks Bundle workflow is defined in:

```text
resources/jobs.yml
```

The workflow runs:

```text
bronze_ingestion
    ↓
silver_chunking
    ↓
gold_embeddings
    ↓
create_azure_search_index
    ↓
upload_gold_to_azure_search
```

Task responsibilities:

* `bronze_ingestion` extracts text and metadata from raw files.
* `silver_chunking` creates AI-ready chunks.
* `gold_embeddings` generates embeddings and writes the Gold Delta table.
* `create_azure_search_index` creates or updates the Azure AI Search index.
* `upload_gold_to_azure_search` reads existing Gold embeddings and uploads them to Azure AI Search.

This automates the cloud-side pipeline from raw Volume data to searchable Azure AI Search chunks.

---

## 17. Design Decisions

### Document download integrated into Databricks

Regulatory document acquisition is fully handled by the Bronze ingestion job. The job downloads documents directly from EUR-Lex via CELEX IDs, eliminating any local download or manual upload step. This keeps the entire ingestion pipeline within the governed Databricks environment.

### Embeddings generated in the Gold layer

The Gold job generates embeddings and stores them in the Gold Delta table. This creates a reusable AI-ready table containing both chunk text and vector embeddings.

The Azure AI Search upload job only uploads existing embeddings from the Gold table. It does not re-embed chunks.

This design avoids unnecessary duplicate embedding generation and makes Azure AI Search index rebuilds faster and cheaper.

### Azure AI Search instead of only Databricks Vector Search

Azure AI Search was used because it integrates well with the FastAPI application layer and supports hybrid retrieval using both keyword and vector search.

### Dockerized local application layer

The local FastAPI application layer is Dockerized for reproducible local execution and presentation. Cloud services such as Databricks, Azure OpenAI, and Azure AI Search remain external managed services.

---

## 18. Current Limitations

Current limitations include:

* simple API key authentication,
* lightweight PII redaction,
* no full user management,
* no production deployment,
* limited evaluation dataset,
* no advanced observability dashboard,
* and no enterprise identity integration.

---

## 19. Future Architecture Improvements

Future improvements include:

* regulation-specific filters,
* semantic reranking,
* Azure Key Vault integration,
* OAuth2 or Azure AD authentication,
* expanded evaluation set,
* adversarial and negative test cases,
* monitoring dashboard,
* automated CI/CD pipeline,
* cloud deployment of the FastAPI/frontend layer,
* and production observability.
