# Final Demo Script

## 1. Purpose

This document defines the recommended final demonstration flow for the AI-Powered Regulatory Compliance Assistant.

The goal of the demo is to show Accenture leadership and technical reviewers that the system works end-to-end, from regulatory data ingestion to grounded AI answer generation and evaluation.

---

## 2. Demo Message

The main message of the demo is:

> We built an end-to-end AI-powered regulatory compliance assistant that ingests EU regulatory documents, processes them through Databricks, indexes them in Azure AI Search, and allows users to ask natural-language compliance questions with grounded answers and source traceability.

---

## 3. Demo Structure

Recommended demo duration:

```text
10–15 minutes
```

Recommended structure:

1. Business problem
2. Architecture overview
3. Data pipeline
4. RAG workflow
5. Live frontend demo
6. Governance and security
7. Evaluation results
8. Limitations and future improvements

---

## 4. Opening

Suggested speaking notes:

> Financial institutions in the EU need to continuously interpret and comply with complex regulations such as GDPR, DORA, PSD2, MiFID II, and the EU AI Act. Searching these documents manually is time-consuming and traditional keyword search does not always provide enough context. Our solution uses Retrieval-Augmented Generation to retrieve relevant regulatory sources and generate grounded answers with traceability.

---

## 5. Architecture Explanation

Show the README or architecture diagram.

Explain the flow:

```text
Regulatory documents
    ↓
Downloader and metadata manifest
    ↓
Databricks Volume
    ↓
Bronze/Silver/Gold Delta tables
    ↓
Azure OpenAI embeddings
    ↓
Azure AI Search
    ↓
FastAPI RAG backend
    ↓
Frontend application
```

Suggested speaking notes:

> We use Databricks for the governed data engineering part of the system. Raw documents are processed into Bronze, Silver, and Gold Delta tables. The Gold table is then embedded using Azure OpenAI and uploaded to Azure AI Search. The application layer uses FastAPI and a frontend to query the index and generate answers with GPT-4o.

---

## 6. Project Structure

Show the project folder in VS Code.

Highlight:

```text
src/jobs/
src/rag_service.py
src/frontend/api.py
src/frontend/index.html
src/governance/pii_redaction.py
src/evaluation/evaluate_rag.py
evaluation/
docs/
resources/jobs.yml
```

Suggested speaking notes:

> The project is structured by responsibility. Databricks jobs are under `src/jobs`, the RAG logic is in `rag_service.py`, the API and frontend are under `src/frontend`, governance controls are under `src/governance`, and evaluation is under `src/evaluation`.

---

## 7. Databricks Pipeline

Show the Databricks workflow or the `resources/jobs.yml` file.

Explain the pipeline:

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

Suggested speaking notes:

> The Databricks workflow automates the data engineering and indexing process. Bronze extracts raw document text, Silver creates AI-ready chunks, Gold prepares the final retrieval table, then the final jobs create the Azure AI Search index and upload embedded chunks.

If available, show the successful Databricks job run and mention:

```text
2733 chunks uploaded to Azure AI Search
```

---

## 8. Azure AI Search

Show the Azure AI Search index or explain it from the code.

Mention the index fields:

```text
chunk_id
chunk_text
embedding
short_title
regulation_title
source_url
page_number
file_name
```

Suggested speaking notes:

> Azure AI Search stores both the regulatory text and the vector embeddings. The system uses hybrid retrieval, combining keyword search and vector similarity, which improves retrieval when users mention exact regulation names such as GDPR or DORA.

---

## 9. Start the Backend

Run:

```powershell
uv run uvicorn src.frontend.api:app --reload
```

Explain:

> The FastAPI backend exposes a `/ask` endpoint. It validates the request, checks the API key, redacts basic PII, sends the question to the RAG service, retrieves relevant chunks, and returns the answer with sources.

---

## 10. Frontend Demo Question 1: GDPR

Open:

```text
src/frontend/index.html
```

Ask:

```text
According to GDPR, what obligations do controllers have for personal data protection?
```

Show:

* answer,
* GDPR sources,
* page numbers,
* source URLs,
* retrieval scores,
* chunk previews.

Suggested speaking notes:

> The answer is grounded in retrieved GDPR chunks. The source cards show exactly where the information came from, including the regulation, page number, file name, and URL.

---

## 11. Frontend Demo Question 2: DORA

Ask:

```text
What kind of operational resilience does DORA focus on?
```

Show that the sources are DORA.

Suggested speaking notes:

> This demonstrates that the assistant can retrieve from a different regulation and answer a financial operational resilience question using DORA sources.

---

## 12. Frontend Demo Question 3: PII Redaction

Ask:

```text
My email is maria.test@example.com. What does GDPR say about the protection of personal data?
```

Show the backend terminal logs if possible.

Expected terminal log:

```text
Original question:
My email is maria.test@example.com. What does GDPR say about the protection of personal data?

Redacted question:
My email is [EMAIL_REDACTED]. What does GDPR say about the protection of personal data?
```

Suggested speaking notes:

> Before the question is sent to the RAG pipeline, the backend applies lightweight PII redaction. This demonstrates a governance control in the application layer.

---

## 13. Authentication Demo

Optional quick test:

Temporarily explain that the `/ask` endpoint requires an `X-API-Key` header.

Suggested speaking notes:

> The API is protected by a basic API key mechanism. Requests without the correct `X-API-Key` are rejected. For production, this would be replaced by OAuth2, JWT, or Azure AD authentication.

Do not spend too much time on this section.

---

## 14. Evaluation Demo

Run:

```powershell
uv run python -m src.evaluation.evaluate_rag
```

Show the summary:

```text
Total questions: 12
Passed questions: 12
Pass rate: 1.0
Questions with sources: 12
Expected regulation found: 12
Top source matches expected: 12
Average keyword coverage: 0.958
Average faithfulness score: 4.917
Groundedness pass count: 12
```

Suggested speaking notes:

> We evaluated the system using 12 benchmark regulatory questions. The evaluation checks retrieval quality, expected regulation matching, keyword coverage, and faithfulness. We also use GPT-4o as an LLM-as-judge evaluator to check whether answers are grounded in the retrieved context.

---

## 15. Explain the Evaluation

Suggested explanation:

> Each question has an expected regulation and expected keywords. The script runs the full RAG pipeline and checks whether sources are returned, whether the expected regulation appears in the retrieved sources, whether the top source is correct, and whether the generated answer contains the expected compliance concepts. Then a GPT-4o judge scores faithfulness from 1 to 5 using only the retrieved source context.

Final result:

```text
12 / 12 passed
100% pass rate
4.917 / 5 average faithfulness score
12 / 12 groundedness pass count
```

---

## 16. Leadership-Level Value

Suggested speaking notes:

> The business value is that compliance teams can ask natural-language questions and quickly receive grounded answers with traceable evidence. This reduces manual search effort, improves knowledge accessibility, and provides a foundation for governed AI adoption in regulated financial environments.

---

## 17. Limitations

Mention honestly:

* API key authentication is demo-level.
* Some PDFs are manually handled.
* Evaluation dataset is lightweight.
* Production deployment would require stronger identity management and monitoring.
* Regulation-specific filters and semantic reranking could improve retrieval further.

Suggested speaking notes:

> The current version is a working project prototype. For production, we would add enterprise authentication, Azure Key Vault, expanded evaluation, semantic reranking, cloud deployment, and observability dashboards.

---

## 18. Closing

Suggested closing:

> In conclusion, the project delivers a complete working RAG system for EU regulatory compliance. It demonstrates data ingestion, Databricks engineering, Azure AI Search indexing, GPT-4o answer generation, API/frontend integration, governance controls, and automated evaluation. The system is ready for demonstration and provides a strong foundation for a production compliance knowledge assistant.
