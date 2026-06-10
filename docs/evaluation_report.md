# RAG Evaluation Report

## 1. Objective

This report summarizes the evaluation of the AI-Powered Regulatory Compliance Assistant.  
The purpose of the evaluation is to verify that the Retrieval-Augmented Generation pipeline can retrieve relevant regulatory sources and generate grounded answers for user questions related to EU financial regulations.

The evaluation focuses on:

- source retrieval availability,
- expected regulation matching,
- top-source correctness,
- keyword coverage in generated answers,
- and retrieval score monitoring.

## 2. Evaluation Dataset

A lightweight benchmark dataset was created with 8 representative compliance questions.

The questions cover the following regulations:

- GDPR
- DORA
- PSD2
- MiFID II
- EU AI Act

Each evaluation item includes:

- a natural-language question,
- the expected regulation,
- and a list of expected keywords.

## 3. Evaluation Method

The evaluation script runs each question through the real RAG pipeline.

For each question, the system checks:

1. Whether the assistant returns retrieved sources.
2. Whether the expected regulation appears in the retrieved sources.
3. Whether the top retrieved source matches the expected regulation.
4. Whether the generated answer contains expected keywords.
5. The average retrieval score of the returned sources.

A question is considered passed when:

- at least one source is returned,
- the expected regulation appears in the retrieved sources,
- and keyword coverage is at least 40%.

## 4. Evaluation Results

The evaluation was executed on the current Azure AI Search index and FastAPI-compatible RAG backend.

Summary results:

| Metric | Result |
|---|---:|
| Total questions | 8 |
| Passed questions | 8 |
| Pass rate | 100% |
| Questions with sources | 8 |
| Expected regulation found | 8 |
| Top source matched expected regulation | 8 |
| Average keyword coverage | 93.8% |

## 5. Interpretation

The evaluation results indicate that the RAG pipeline retrieves relevant regulatory evidence and generates answers that contain the expected compliance concepts.

All test questions returned sources, and the expected regulation was present in the retrieved results for every question. In all 8 cases, the top retrieved source matched the expected regulation. This shows that the retrieval layer is functioning correctly for the tested regulatory domains.

The average keyword coverage was 93.8%, meaning that the generated answers generally included the expected domain-specific terms.

## 6. Observed Limitations

Although all evaluation questions passed, some lower-ranked retrieved sources came from other regulations. For example, some DORA and PSD2 questions retrieved relevant top sources but also included lower-ranked chunks from other regulatory documents.

This behavior is expected in a semantic and hybrid retrieval system, where documents can share related concepts such as risk, security, governance, and financial services.

Possible improvements include:

- applying regulation-specific filters when the user explicitly mentions a regulation,
- increasing metadata-based filtering,
- tuning chunk size and overlap,
- adding reranking,
- expanding the evaluation dataset,
- and adding human review for answer quality.

## 7. Monitoring Metrics

The evaluation pipeline provides simple monitoring metrics that can be tracked over time:

- pass rate,
- number of questions with sources,
- expected regulation match rate,
- top-source match rate,
- keyword coverage,
- and average retrieval score.

These metrics can be used after changes to chunking, embeddings, indexing, or prompt design to confirm that retrieval quality has not degraded.

## 8. Conclusion

The evaluation confirms that the current RAG implementation is ready for demonstration.  
The system successfully retrieves relevant regulatory sources, generates grounded answers, and provides traceability through source metadata such as regulation title, file name, page number, and source URL.