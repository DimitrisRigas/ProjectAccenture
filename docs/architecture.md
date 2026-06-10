# System Architecture

## 1. Overview

The AI-Powered Regulatory Compliance Assistant is an end-to-end Retrieval-Augmented Generation system for EU financial regulatory documents.

The system ingests regulatory documents, processes them into AI-ready chunks, creates embeddings, indexes them in Azure AI Search, and exposes a FastAPI and frontend interface for natural-language question answering.

The architecture combines:

* Databricks for governed data engineering,
* Delta Lake for Bronze/Silver/Gold processing,
* Azure OpenAI for embeddings and answer generation,
* Azure AI Search for vector and hybrid retrieval,
* FastAPI for the API layer,
* and a browser frontend for user interaction.

---

## 2. High-Level Architecture

```text
Regulatory Sources
    ↓
Downloader and Metadata Manifest
    ↓
Databricks Unity Catalog Volume
    ↓
Bronze Delta Tables
    ↓
Silver Chunking
    ↓
Gold Retrieval Table
    ↓
Azure OpenAI Embeddings
    ↓
Azure AI Search Index
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

| Layer                  | Purpose                                     | Implementation                              |
| ---------------------- | ------------------------------------------- | ------------------------------------------- |
| Data Sources Layer     | Collect regulatory documents                | EUR-Lex, EBA, ECB sources                   |
| Ingestion Layer        | Download and prepare files                  | `src/downloader.py`, `src/uploader.py`      |
| Data Engineering Layer | Transform raw data into AI-ready tables     | Databricks, PySpark, Delta Lake             |
| AI Processing Layer    | Generate embeddings and LLM responses       | Azure OpenAI                                |
| Retrieval Layer        | Retrieve relevant regulatory chunks         | Azure AI Search                             |
| RAG Layer              | Build context and generate grounded answers | `src/rag_service.py`                        |
| API Layer              | Expose question-answering endpoint          | FastAPI `/ask`                              |
| Application Layer      | User interface                              | HTML/CSS/JavaScript frontend                |
| Governance Layer       | Secrets, PII, traceability                  | Databricks Secrets, PII redaction, metadata |
| Evaluation Layer       | Measure retrieval and answer quality        | `src/evaluation/evaluate_rag.py`            |

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

The ingestion layer begins locally with:

```text
src/downloader.py
src/uploader.py
```

The downloader prepares the regulatory dataset and creates:

```text
data/metadata/document_manifest.json
```

The uploader transfers raw files and metadata into a Databricks Unity Catalog Volume.

This separates local document acquisition from cloud-based data engineering. The current design is practical because some EUR-Lex PDFs may require manual handling before upload.

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

### Gold Layer

The Gold layer prepares the final clean retrieval table.

Main job:

```text
src/jobs/gold_embeddings.py
```

Output:

```text
accenture2026dbcks.team4.gold_document_embeddings
```

This table contains clean chunk text and metadata used by the embedding and indexing process.

The Gold job does not generate embeddings directly. Instead, it prepares the final dataset that is later embedded and uploaded to Azure AI Search.

---

## 7. Azure AI Search and Embeddings

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

This job:

1. Reads rows from the Gold Delta table.
2. Sends chunk text to Azure OpenAI for embedding generation.
3. Receives vector embeddings.
4. Uploads chunk text, metadata, and embeddings to Azure AI Search.

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

## 12. Governance and Security

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

## 13. Evaluation and Monitoring

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

## 14. Databricks Workflow

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

This automates the cloud-side pipeline from raw Volume data to searchable Azure AI Search chunks.

---

## 15. Design Decisions

### Local downloader and uploader

The downloader and uploader are kept local because some regulatory PDFs may require manual handling. This makes the ingestion process more reliable for the current project.

A future improvement would be to move document acquisition into a Databricks job.

### Embeddings outside the Gold job

The Gold job prepares clean retrieval data, while `upload_gold_to_azure_search.py` creates embeddings and uploads to Azure AI Search. This separation keeps the Delta table preparation independent from the external Azure indexing process.

### Azure AI Search instead of only Databricks Vector Search

Azure AI Search was used because it integrates well with the FastAPI application layer and supports hybrid retrieval using both keyword and vector search.

---

## 16. Current Limitations

Current limitations include:

* manual handling for some source documents,
* simple API key authentication,
* lightweight PII redaction,
* no full user management,
* no production deployment,
* limited evaluation dataset,
* and no advanced observability dashboard.

---

## 17. Future Architecture Improvements

Future improvements include:

* cloud-native downloader job inside Databricks,
* regulation-specific filters,
* semantic reranking,
* Azure Key Vault integration,
* OAuth2 or Azure AD authentication,
* expanded evaluation set,
* adversarial and negative test cases,
* monitoring dashboard,
* Dockerized deployment,
* and CI/CD automation.
