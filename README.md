# AI-Powered Regulatory Compliance Assistant

## 1. Project Overview

The AI-Powered Regulatory Compliance Assistant is an end-to-end Retrieval-Augmented Generation application designed for EU financial regulatory knowledge discovery.

The system enables users to ask natural-language questions about European Union regulations and receive grounded answers based on retrieved regulatory sources. Each answer includes source traceability such as regulation name, file name, page number, retrieval score, and source URL.

The project combines Databricks, Delta Lake, Azure OpenAI, Azure AI Search, FastAPI, and a web frontend to create a governed AI knowledge engineering pipeline for regulatory compliance use cases.

---

## 2. Business Problem

Financial institutions operating in the European Union must comply with a complex and evolving regulatory landscape that includes GDPR, DORA, PSD2, MiFID II, and the EU AI Act.

Compliance officers, auditors, legal teams, and risk managers frequently need to search large regulatory documents to identify obligations, understand operational requirements, validate controls, and respond to regulatory questions.

Traditional keyword search is often insufficient because regulatory questions require:

* semantic understanding,
* cross-document retrieval,
* traceable source references,
* grounded answer generation,
* and governance controls.

This project addresses the problem by implementing a RAG-based compliance assistant that retrieves relevant regulatory chunks and generates source-grounded answers.

---

## 3. Main Capabilities

The system supports:

* regulatory document acquisition,
* metadata manifest creation,
* upload to Databricks Unity Catalog Volume,
* Bronze/Silver/Gold Delta table processing,
* PDF, HTML, and XML text extraction,
* AI-ready chunking with metadata and lineage,
* Azure OpenAI embedding generation,
* Azure AI Search vector and hybrid retrieval,
* GPT-4o answer generation,
* FastAPI `/ask` endpoint,
* API key authentication,
* PII redaction,
* web frontend interface,
* source traceability,
* automated RAG evaluation,
* and LLM-as-judge groundedness evaluation.

---

## 4. High-Level Architecture

```text
Regulatory Sources
    ↓
Local Downloader
    ↓
Metadata Manifest
    ↓
Databricks Volume Upload
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
GPT-4o RAG Answer Generation
    ↓
FastAPI Backend
    ↓
Frontend Application
```

---

## 5. Architecture Layers

| Layer                         | Implementation                                            |
| ----------------------------- | --------------------------------------------------------- |
| Data Sources Layer            | EUR-Lex PDFs, EBA HTML, ECB XML                           |
| Ingestion Layer               | `src/downloader.py`, `src/uploader.py`                    |
| Data Engineering Layer        | Databricks jobs, Bronze/Silver/Gold Delta tables          |
| AI Processing Layer           | Azure OpenAI embeddings and GPT-4o                        |
| Retrieval Layer               | Azure AI Search vector and hybrid retrieval               |
| RAG Layer                     | `src/rag_service.py`                                      |
| API & Application Layer       | FastAPI backend and HTML/CSS/JavaScript frontend          |
| Governance & Security Layer   | Databricks secrets, API key authentication, PII redaction |
| Evaluation & Monitoring Layer | Automated evaluation script and evaluation report         |

---

## 6. Project Structure

```text
ProjectAccenture/
│
├── data/
│   ├── manual/
│   ├── metadata/
│   └── raw/
│
├── docs/
│   └── evaluation_report.md
│
├── evaluation/
│   ├── evaluation_questions.json
│   └── evaluation_results.json
│
├── resources/
│   └── jobs.yml
│
├── src/
│   ├── evaluation/
│   │   └── evaluate_rag.py
│   │
│   ├── frontend/
│   │   ├── api.py
│   │   └── index.html
│   │
│   ├── governance/
│   │   └── pii_redaction.py
│   │
│   ├── jobs/
│   │   ├── bronze_ingestion.py
│   │   ├── silver_chunking.py
│   │   ├── gold_embeddings.py
│   │   ├── create_azure_search_index.py
│   │   └── upload_gold_to_azure_search.py
│   │
│   ├── config.py
│   ├── downloader.py
│   ├── rag_service.py
│   └── uploader.py
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── databricks.yml
├── pyproject.toml   
├── uv.lock
└── README.md
```

---

## 7. Main Components

### 7.1 Regulatory Downloader

File:

```text
src/downloader.py
```

The downloader prepares the regulatory dataset by collecting or registering regulatory documents. It supports manual PDF handling for documents that are difficult to download automatically and creates a metadata manifest for downstream processing.

The downloader prepares:

* GDPR PDF
* DORA PDF
* PSD2 PDF
* MiFID II PDF
* EU AI Act PDF
* EBA HTML source
* ECB XML source

It creates the manifest at:

```text
data/metadata/document_manifest.json
```

---

### 7.2 Databricks Volume Uploader

File:

```text
src/uploader.py
```

The uploader transfers local raw documents and metadata into a Databricks Unity Catalog Volume.

The Databricks Volume acts as the governed storage layer for raw regulatory documents before they are processed into Delta tables.

---

### 7.3 Bronze Ingestion

File:

```text
src/jobs/bronze_ingestion.py
```

The Bronze job reads the metadata manifest and raw files from the Databricks Volume.

It extracts text from:

* PDF files,
* HTML files,
* XML files.

It writes the extracted data into Bronze Delta tables:

```text
accenture2026dbcks.team4.bronze_regulatory_documents
accenture2026dbcks.team4.bronze_document_pages
```

The Bronze layer keeps raw extracted text, document metadata, source provenance, and page-level information.

---

### 7.4 Silver Chunking

File:

```text
src/jobs/silver_chunking.py
```

The Silver job converts extracted document text into AI-ready chunks.

It uses overlapping chunking to preserve context across long regulatory documents.

The output table is:

```text
accenture2026dbcks.team4.silver_document_chunks
```

Each chunk includes:

* chunk ID,
* document ID,
* regulation title,
* short title,
* page number,
* section number,
* source URL,
* file name,
* chunk text,
* chunk length,
* and lineage metadata.

---

### 7.5 Gold Retrieval Table

File:

```text
src/jobs/gold_embeddings.py
```

The Gold job prepares the final clean retrieval table used before embedding and indexing.

The output table is:

```text
accenture2026dbcks.team4.gold_document_embeddings
```

Despite the file name, this job does not create embeddings directly. It prepares the clean AI-ready Gold dataset with chunk text and metadata.

Embedding generation happens later in the Azure AI Search upload job.

---

### 7.6 Azure AI Search Index Creation

File:

```text
src/jobs/create_azure_search_index.py
```

This job creates or updates the Azure AI Search index.

The index contains:

* `chunk_id`
* `chunk_text`
* `embedding`
* `short_title`
* `regulation_title`
* `source_url`
* `page_number`
* `file_name`

The vector field uses 1536 dimensions, matching the Azure OpenAI `text-embedding-3-small` embedding model.

The index supports vector retrieval and hybrid search.

---

### 7.7 Embedding Generation and Azure AI Search Upload

File:

```text
src/jobs/upload_gold_to_azure_search.py
```

This job reads rows from the Gold Delta table, generates embeddings using Azure OpenAI, and uploads the final documents to Azure AI Search.

The job performs:

1. Read Gold chunks from Databricks.
2. Generate embeddings in batches.
3. Attach metadata to each chunk.
4. Upload documents to Azure AI Search.

The final Azure AI Search index stores both the chunk text and its vector embedding.

---

### 7.8 RAG Service

File:

```text
src/rag_service.py
```

The RAG service is the core application logic.

It performs:

1. User question embedding.
2. Hybrid retrieval from Azure AI Search.
3. Context construction from retrieved sources.
4. GPT-4o answer generation.
5. Source formatting for the API and frontend.

Hybrid retrieval combines:

* keyword search,
* vector similarity search.

This improves retrieval quality when users mention exact regulation names such as GDPR, DORA, PSD2, MiFID II, or AI Act.

The RAG prompt is designed to enforce:

* grounded answers,
* source citations,
* no hallucinated legal claims,
* clear compliance-oriented structure,
* and uncertainty handling when retrieved context is insufficient.

---

### 7.9 FastAPI Backend

File:

```text
src/frontend/api.py
```

The FastAPI backend exposes the main API endpoint:

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

The API returns:

```json
{
  "question": "...",
  "answer": "...",
  "sources": [...]
}
```

The backend includes:

* request validation,
* CORS support,
* API key authentication using `X-API-Key`,
* PII redaction before RAG execution,
* and error handling.

---

### 7.10 Frontend Application

File:

```text
src/frontend/index.html
```

The frontend provides a browser-based interface where users can ask regulatory questions and inspect retrieved sources.

It displays:

* generated answer,
* retrieved source cards,
* regulation title,
* page number,
* file name,
* source URL,
* retrieval score,
* and chunk preview.

---

### 7.11 Governance and PII Redaction

File:

```text
src/governance/pii_redaction.py
```

The governance module implements lightweight PII detection and redaction before user questions are sent to the RAG pipeline.

It redacts:

* email addresses,
* phone numbers,
* IBAN-like identifiers,
* credit-card-like numbers.

Example:

```text
My email is test@example.com. What does GDPR say about personal data?
```

becomes:

```text
My email is [EMAIL_REDACTED]. What does GDPR say about personal data?
```

This provides a basic responsible AI and privacy control for the application layer.

---

### 7.12 Evaluation Pipeline

Files:

```text
src/evaluation/evaluate_rag.py
evaluation/evaluation_questions.json
evaluation/evaluation_results.json
docs/evaluation_report.md
```

The evaluation pipeline tests the real RAG system using a benchmark dataset of 12 regulatory questions.

It checks:

* whether sources are returned,
* whether the expected regulation appears in retrieved sources,
* whether the top source matches the expected regulation,
* keyword coverage,
* average retrieval score,
* faithfulness / groundedness,
* and unsupported claims.

The faithfulness check uses an LLM-as-judge approach. GPT-4o evaluates whether the generated answer is supported by the retrieved source context.

Final evaluation result:

| Metric                                 |    Result |
| -------------------------------------- | --------: |
| Total questions                        |        12 |
| Passed questions                       |        12 |
| Pass rate                              |      100% |
| Questions with sources                 |        12 |
| Expected regulation found              |        12 |
| Top source matched expected regulation |        12 |
| Average keyword coverage               |     95.8% |
| Average faithfulness score             | 4.917 / 5 |
| Groundedness pass count                |   12 / 12 |

---

## 8. Configuration

The project uses a local `.env` file for local development.

Example:

```env
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=your-gpt-4o-deployment

EMBEDDING_MODEL_NAME=text-embedding-3-small

AI_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AI_SEARCH_API_KEY=your-search-key
AI_SEARCH_INDEX_NAME=team4

AI_SEARCH_VECTOR_FIELD=embedding
AI_SEARCH_CONTENT_FIELD=chunk_text

APP_API_KEY=demo-secret-key

TOP_K=5
```

The `.env` file should not be committed to Git.

In Databricks jobs, secrets are loaded from Databricks Secrets using the configured secret scope.

---

## 9. Databricks Workflow

The Databricks job pipeline is defined in:

```text
resources/jobs.yml
```

The pipeline runs the following tasks:

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

The workflow performs the full data engineering and indexing process from raw documents to searchable Azure AI Search chunks.

---

## 10. How to Run Locally

### 10.1 Install dependencies

```powershell
uv sync
```

or:

```powershell
uv install
```

---

### 10.2 Run the downloader

```powershell
uv run python src/downloader.py
```

---

### 10.3 Upload files to Databricks Volume

```powershell
uv run python src/uploader.py
```

---

### 10.4 Deploy and run Databricks Bundle

Validate the bundle:

```powershell
databricks bundle validate -p train13
```

Deploy the bundle:

```powershell
databricks bundle deploy -p train13
```

Run the workflow:

```powershell
databricks bundle run regulatory_compliance_pipeline -p train13
```

---

### 10.5 Run the FastAPI backend

```powershell
uv run uvicorn src.frontend.api:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

Swagger documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

### 10.6 Open the frontend

Open:

```text
src/frontend/index.html
```

in a browser.

The frontend sends requests to:

```text
http://127.0.0.1:8000/ask
```

---
## Running with Docker

The local application layer can also be run with Docker.

Docker is used for the FastAPI backend, RAG service, API key authentication, and PII redaction layer. The cloud services remain external managed services:

* Databricks workflows remain in Databricks.
* Azure OpenAI remains an external Azure service.
* Azure AI Search remains an external Azure service.
* Unity Catalog Volumes and Delta tables remain in Databricks.

The Docker container runs the local API layer and connects to Azure OpenAI and Azure AI Search using environment variables.

### Dockerized Components

The Docker container includes:

* FastAPI backend
* `/ask` endpoint
* RAG service
* Azure AI Search retrieval client
* Azure OpenAI client
* PII redaction logic
* API key authentication

### Files

Docker configuration is defined in:

```text
Dockerfile
docker-compose.yml
.dockerignore
```

### Run with Docker Compose

From the project root, run:

```powershell
docker compose up --build
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### Test the Dockerized API

```powershell
curl -X POST "http://127.0.0.1:8000/ask" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: demo-secret-key" `
  -d "{\"question\":\"According to GDPR, what obligations do controllers have for personal data protection?\",\"top_k\":5}"
```

### Test with the Frontend

After Docker is running, open:

```text
src/frontend/index.html
```

Then ask:

```text
According to GDPR, what obligations do controllers have for personal data protection?
```

If the frontend returns an answer with retrieved sources, the Dockerized API is working correctly.

### Stop Docker

```powershell
docker compose down
```

### Notes

The `.env` file is loaded at runtime through Docker Compose. It is not copied into the Docker image and must not be committed to Git.

This setup Dockerizes the local application layer only. Databricks and Azure services are intentionally kept as external cloud services.

## 11. Example API Request

```powershell
curl -X POST "http://127.0.0.1:8000/ask" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: demo-secret-key" `
  -d "{\"question\":\"According to GDPR, what obligations do controllers have for personal data protection?\",\"top_k\":5}"
```

---

## 12. Example Questions

Useful demo questions:

```text
According to GDPR, what obligations do controllers have for personal data protection?
```

```text
What does DORA require from financial entities?
```

```text
What is the purpose of PSD2?
```

```text
How does MiFID II relate to investor protection?
```

```text
What does the AI Act say about high-risk AI systems?
```

```text
My email is maria.test@example.com. What does GDPR say about the protection of personal data?
```

---

## 13. Evaluation

Run the evaluation pipeline:

```powershell
uv run python -m src.evaluation.evaluate_rag
```

The script reads:

```text
evaluation/evaluation_questions.json
```

and writes:

```text
evaluation/evaluation_results.json
```

A detailed explanation is available in:

```text
docs/evaluation_report.md
```

---

## 14. Security and Governance

The project includes several security and governance controls:

* secrets are excluded from Git,
* local secrets are loaded from `.env`,
* Databricks jobs use Databricks Secrets,
* API access is protected using an `X-API-Key` header,
* user questions are processed through PII redaction,
* retrieved sources include traceability metadata,
* answers are constrained by a grounded system prompt,
* and evaluation includes faithfulness / groundedness checks.

For production, API key authentication should be replaced with enterprise authentication such as OAuth2, JWT, Azure AD, or managed identity.

---

## 15. Current Limitations

Current limitations include:

* manual PDF handling is still required for some EUR-Lex documents,
* the frontend API key is visible in browser JavaScript and is only suitable for demonstration,
* the evaluation dataset is lightweight and should be expanded for production,
* there is no full user management system,
* semantic reranking could be added,
* regulation-specific metadata filters could further improve retrieval,
* and production deployment would require stronger monitoring, authentication, and infrastructure automation.

---

## 16. Future Improvements

Future improvements include:

* moving the downloader fully into a Databricks job-Eurlex issue,
* adding regulation-specific filters when a question explicitly mentions a regulation,
* adding semantic reranking,
* expanding evaluation questions,
* adding negative and adversarial test cases,
* adding more advanced PII detection,
* integrating Azure Key Vault,
* adding OAuth2/JWT authentication,
* adding production observability dashboards,
* and deploying the frontend/backend to a cloud application platform.

---

## 17. Final Demonstration Flow

The recommended final demo flow is:

1. Show the business problem.
2. Show the architecture diagram.
3. Show the project structure.
4. Run or show the Databricks pipeline.
5. Show the Azure AI Search index.
6. Start the FastAPI backend.
7. Ask a GDPR question in the frontend.
8. Show the generated answer and retrieved sources.
9. Ask a question with PII and explain redaction.
10. Show the evaluation results.
11. Explain limitations and future improvements.

---

## 18. Final Result

The project delivers a working AI-powered regulatory compliance assistant with an end-to-end data and AI pipeline.

It demonstrates:

* governed regulatory data ingestion,
* Databricks-based data engineering,
* AI-ready document chunking,
* Azure OpenAI embeddings,
* Azure AI Search hybrid retrieval,
* GPT-4o answer generation,
* API and frontend integration,
* source traceability,
* PII redaction,
* authentication,
* and automated RAG evaluation.

The final system is ready for demonstration to business and technical stakeholders.
