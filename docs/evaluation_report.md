# RAG Evaluation Report

## 1. Objective

This report summarizes the evaluation of the AI-Powered Regulatory Compliance Assistant.

The purpose of the evaluation is to verify that the Retrieval-Augmented Generation pipeline can retrieve relevant regulatory sources and generate grounded answers for user questions related to EU financial regulations.

The evaluation focuses on:

* source retrieval availability,
* expected regulation matching,
* top-source correctness,
* keyword coverage in generated answers,
* retrieval score monitoring,
* and faithfulness / groundedness of the generated answers.

## 2. Evaluation Dataset

A lightweight benchmark dataset was created with 12 representative compliance questions.

The questions cover the following regulations:

* GDPR
* DORA
* PSD2
* MiFID II
* EU AI Act

The dataset includes:

* direct regulation-specific questions,
* broader compliance questions,
* a PII-containing question,
* and regulation-identification questions.

Each evaluation item includes:

* a natural-language question,
* the expected regulation,
* and a list of expected keywords.

## 3. Evaluation Method

The evaluation script runs each question through the real RAG pipeline.

For each question, the system checks:

1. Whether the assistant returns retrieved sources.
2. Whether the expected regulation appears in the retrieved sources.
3. Whether the top retrieved source matches the expected regulation.
4. Whether the generated answer contains expected keywords.
5. The average retrieval score of the returned sources.
6. Whether the generated answer is faithful to the retrieved source context.

A question is considered passed when:

* at least one source is returned,
* the expected regulation appears in the retrieved sources,
* keyword coverage is at least 40%,
* and the answer passes the faithfulness / groundedness check.

The faithfulness and groundedness check is implemented using an LLM-as-judge approach. The evaluator receives the user question, the generated answer, and the retrieved source context. It then returns a faithfulness score from 1 to 5, a groundedness pass/fail decision, unsupported claims, and an explanation.

The faithfulness scoring scale is:

* 1 = mostly unsupported or hallucinated
* 2 = several important unsupported claims
* 3 = partially supported, but some claims are unclear or weakly supported
* 4 = mostly supported, with minor unsupported or vague claims
* 5 = fully supported by the retrieved context

A groundedness pass is assigned when the faithfulness score is 4 or 5.

## 4. Evaluation Results

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

## 5. Interpretation

The evaluation results indicate that the RAG pipeline retrieves relevant regulatory evidence and generates answers that contain the expected compliance concepts.

All 12 test questions returned sources, and the expected regulation was present in the retrieved results for every question. In all 12 cases, the top retrieved source matched the expected regulation. This shows that the retrieval layer is functioning correctly for the tested regulatory domains.

The average keyword coverage was 95.8%, meaning that the generated answers generally included the expected domain-specific terms.

The average faithfulness score was 4.917 / 5, and all 12 answers passed the groundedness check. This indicates that the generated answers were strongly supported by the retrieved source context.

## 6. Observed Limitations

Although all evaluation questions passed, some lower-ranked retrieved sources may come from other regulations. For example, DORA, PSD2, MiFID II, GDPR, and AI Act documents can share related concepts such as risk, security, governance, data protection, financial services, and compliance obligations.

This behavior is expected in a semantic and hybrid retrieval system, where different regulatory documents may contain overlapping terminology and related compliance concepts.

Possible improvements include:

* applying regulation-specific filters when the user explicitly mentions a regulation,
* increasing metadata-based filtering,
* tuning chunk size and overlap,
* adding semantic reranking,
* expanding the evaluation dataset,
* adding more difficult negative test cases,
* and adding human review for answer quality.

## 7. Monitoring Metrics

The evaluation pipeline provides simple monitoring metrics that can be tracked over time:

* pass rate,
* number of questions with sources,
* expected regulation match rate,
* top-source match rate,
* keyword coverage,
* average retrieval score,
* faithfulness score,
* groundedness pass rate,
* and unsupported claim detection.

These metrics can be used after changes to chunking, embeddings, indexing, retrieval configuration, or prompt design to confirm that retrieval and answer quality have not degraded.

## 8. Conclusion

The final evaluation dataset contains 12 questions covering GDPR, DORA, PSD2, MiFID II, and the EU AI Act. The dataset includes direct regulation-specific questions, broader compliance questions, a PII-containing question, and regulation-identification questions.

The system passed all 12 questions, achieving a 100% pass rate. All questions returned sources, the expected regulation was found in all cases, and the top retrieved source matched the expected regulation for every question.

The average keyword coverage was 95.8%, and the average faithfulness score was 4.917 / 5. All 12 answers passed the groundedness check.

Overall, the evaluation confirms that the current RAG implementation is ready for demonstration. The system successfully retrieves relevant regulatory sources, generates grounded answers, and provides traceability through source metadata such as regulation title, file name, page number, retrieval score, and source URL.
