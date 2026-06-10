"""
src/evaluation/evaluate_rag.py

Lightweight RAG evaluation script.

This script evaluates the compliance assistant using a small benchmark dataset.

It checks:
- whether the assistant returns sources
- whether the expected regulation appears in retrieved sources
- whether the top source is from the expected regulation
- whether expected keywords appear in the generated answer
- average retrieval score
- faithfulness / groundedness using GPT-4o as a judge

Output:
    evaluation/evaluation_results.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import AzureOpenAI

from src.rag_service import (
    AZURE_OPENAI_DEPLOYMENT_NAME,
    answer_question,
    get_openai_client,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EVALUATION_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "evaluation_questions.json"
EVALUATION_RESULTS_PATH = PROJECT_ROOT / "evaluation" / "evaluation_results.json"

TOP_K = 5


# =============================================================================
# Loading
# =============================================================================

def load_evaluation_questions() -> list[dict[str, Any]]:
    """
    Load evaluation questions from JSON.
    """

    with EVALUATION_QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


# =============================================================================
# Utility functions
# =============================================================================

def normalize_text(value: str | None) -> str:
    """
    Normalize text for simple comparisons.
    """

    if value is None:
        return ""

    return value.lower().replace("-", " ").replace("_", " ").strip()


def safe_json_loads(value: str) -> dict[str, Any]:
    """
    Safely parse JSON returned by the evaluator model.

    If parsing fails, return a fallback result instead of crashing the evaluation.
    """

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {
            "faithfulness_score": 0,
            "groundedness_pass": False,
            "unsupported_claims": [
                "Evaluator did not return valid JSON."
            ],
            "explanation": value[:500],
        }


# =============================================================================
# Retrieval evaluation
# =============================================================================

def check_expected_regulation(
    sources: list[dict[str, Any]],
    expected_regulation: str,
) -> dict[str, Any]:
    """
    Check if expected regulation appears in retrieved sources.
    """

    expected_normalized = normalize_text(expected_regulation)

    source_titles = [
        source.get("short_title")
        for source in sources
    ]

    normalized_titles = [
        normalize_text(title)
        for title in source_titles
    ]

    expected_found = any(
        expected_normalized in title
        or title in expected_normalized
        for title in normalized_titles
    )

    top_source_title = sources[0].get("short_title") if sources else None
    top_source_matches = False

    if top_source_title:
        top_source_normalized = normalize_text(top_source_title)
        top_source_matches = (
            expected_normalized in top_source_normalized
            or top_source_normalized in expected_normalized
        )

    return {
        "expected_regulation": expected_regulation,
        "retrieved_source_titles": source_titles,
        "expected_regulation_found": expected_found,
        "top_source_title": top_source_title,
        "top_source_matches_expected": top_source_matches,
    }


def check_keyword_coverage(
    answer: str,
    expected_keywords: list[str],
) -> dict[str, Any]:
    """
    Check how many expected keywords appear in the generated answer.
    """

    answer_normalized = normalize_text(answer)

    found_keywords = []
    missing_keywords = []

    for keyword in expected_keywords:
        keyword_normalized = normalize_text(keyword)

        if keyword_normalized in answer_normalized:
            found_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)

    coverage = (
        len(found_keywords) / len(expected_keywords)
        if expected_keywords
        else 0.0
    )

    return {
        "expected_keywords": expected_keywords,
        "found_keywords": found_keywords,
        "missing_keywords": missing_keywords,
        "keyword_coverage": round(coverage, 3),
    }


def calculate_average_score(
    sources: list[dict[str, Any]],
) -> float | None:
    """
    Calculate average retrieval score from returned sources.
    """

    scores = [
        source.get("score")
        for source in sources
        if source.get("score") is not None
    ]

    if not scores:
        return None

    return round(sum(scores) / len(scores), 6)


# =============================================================================
# Faithfulness / groundedness evaluation
# =============================================================================

def build_source_context_for_judge(
    sources: list[dict[str, Any]],
) -> str:
    """
    Build a compact source context from returned RAG sources.

    The judge checks whether the generated answer is supported by this context.
    """

    context_parts = []

    for source in sources:
        source_number = source.get("source_number", "N/A")
        short_title = source.get("short_title", "N/A")
        regulation_title = source.get("regulation_title", "N/A")
        file_name = source.get("file_name", "N/A")
        page_number = source.get("page_number", "N/A")
        chunk_preview = source.get("chunk_preview", "")

        context_parts.append(
            f"[Source {source_number}]\n"
            f"Short title: {short_title}\n"
            f"Regulation title: {regulation_title}\n"
            f"File name: {file_name}\n"
            f"Page number: {page_number}\n"
            f"Text preview:\n{chunk_preview}"
        )

    return "\n\n".join(context_parts)


def evaluate_faithfulness_with_llm(
    openai_client: AzureOpenAI,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Use GPT-4o as a judge to evaluate answer faithfulness / groundedness.

    The judge must only check whether the answer is supported by the retrieved sources.
    """

    source_context = build_source_context_for_judge(sources)

    system_message = """
You are a strict RAG evaluation judge.

Your task is to evaluate whether the generated answer is faithful to the retrieved source context.

Do not judge whether the answer is legally complete.
Do not use outside knowledge.
Only check if the answer is supported by the retrieved sources.

Return only valid JSON with this exact schema:

{
  "faithfulness_score": 1,
  "groundedness_pass": false,
  "unsupported_claims": [],
  "explanation": ""
}

Scoring:
1 = mostly unsupported or hallucinated
2 = several important unsupported claims
3 = partially supported, but some claims are unclear or weakly supported
4 = mostly supported, with minor unsupported or vague claims
5 = fully supported by the retrieved context

groundedness_pass should be true only if score is 4 or 5.
"""

    user_message = f"""
Question:
{question}

Generated answer:
{answer}

Retrieved source context:
{source_context}

Evaluate faithfulness now.
"""

    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {
                "role": "system",
                "content": system_message.strip(),
            },
            {
                "role": "user",
                "content": user_message.strip(),
            },
        ],
        temperature=0,
        response_format={
            "type": "json_object",
        },
    )

    content = response.choices[0].message.content or "{}"
    parsed = safe_json_loads(content)

    faithfulness_score = parsed.get("faithfulness_score", 0)

    try:
        faithfulness_score = int(faithfulness_score)
    except (TypeError, ValueError):
        faithfulness_score = 0

    groundedness_pass = parsed.get("groundedness_pass", False)

    if not isinstance(groundedness_pass, bool):
        groundedness_pass = faithfulness_score >= 4

    unsupported_claims = parsed.get("unsupported_claims", [])

    if not isinstance(unsupported_claims, list):
        unsupported_claims = [str(unsupported_claims)]

    explanation = parsed.get("explanation", "")

    return {
        "faithfulness_score": faithfulness_score,
        "groundedness_pass": groundedness_pass,
        "unsupported_claims": unsupported_claims,
        "explanation": explanation,
    }


# =============================================================================
# Single question evaluation
# =============================================================================

def evaluate_single_question(
    item: dict[str, Any],
    openai_client: AzureOpenAI,
) -> dict[str, Any]:
    """
    Evaluate one question.
    """

    question_id = item["id"]
    question = item["question"]
    expected_regulation = item["expected_regulation"]
    expected_keywords = item["expected_keywords"]

    print("=" * 100)
    print(f"Evaluating {question_id}")
    print(question)
    print("=" * 100)

    result = answer_question(
        question=question,
        top_k=TOP_K,
    )

    answer = result.get("answer", "")
    sources = result.get("sources", [])

    has_sources = len(sources) > 0

    regulation_check = check_expected_regulation(
        sources=sources,
        expected_regulation=expected_regulation,
    )

    keyword_check = check_keyword_coverage(
        answer=answer,
        expected_keywords=expected_keywords,
    )

    average_score = calculate_average_score(sources)

    faithfulness_check = evaluate_faithfulness_with_llm(
        openai_client=openai_client,
        question=question,
        answer=answer,
        sources=sources,
    )

    passed = (
        has_sources
        and regulation_check["expected_regulation_found"]
        and keyword_check["keyword_coverage"] >= 0.4
        and faithfulness_check["groundedness_pass"]
    )

    evaluation_result = {
        "id": question_id,
        "question": question,
        "passed": passed,
        "has_sources": has_sources,
        "num_sources": len(sources),
        "average_retrieval_score": average_score,
        "regulation_check": regulation_check,
        "keyword_check": keyword_check,
        "faithfulness_check": faithfulness_check,
        "answer_preview": answer[:700],
    }

    print(f"Passed: {passed}")
    print(f"Expected regulation found: {regulation_check['expected_regulation_found']}")
    print(f"Top source matches expected: {regulation_check['top_source_matches_expected']}")
    print(f"Keyword coverage: {keyword_check['keyword_coverage']}")
    print(f"Faithfulness score: {faithfulness_check['faithfulness_score']}")
    print(f"Groundedness pass: {faithfulness_check['groundedness_pass']}")
    print(f"Number of sources: {len(sources)}")
    print()

    return evaluation_result


# =============================================================================
# Summary
# =============================================================================

def summarize_results(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Create summary metrics.
    """

    total_questions = len(results)
    passed_questions = sum(1 for result in results if result["passed"])

    pass_rate = (
        passed_questions / total_questions
        if total_questions
        else 0.0
    )

    questions_with_sources = sum(
        1
        for result in results
        if result["has_sources"]
    )

    expected_regulation_found = sum(
        1
        for result in results
        if result["regulation_check"]["expected_regulation_found"]
    )

    top_source_matches = sum(
        1
        for result in results
        if result["regulation_check"]["top_source_matches_expected"]
    )

    keyword_coverages = [
        result["keyword_check"]["keyword_coverage"]
        for result in results
    ]

    average_keyword_coverage = (
        sum(keyword_coverages) / len(keyword_coverages)
        if keyword_coverages
        else 0.0
    )

    faithfulness_scores = [
        result["faithfulness_check"]["faithfulness_score"]
        for result in results
    ]

    average_faithfulness_score = (
        sum(faithfulness_scores) / len(faithfulness_scores)
        if faithfulness_scores
        else 0.0
    )

    groundedness_pass_count = sum(
        1
        for result in results
        if result["faithfulness_check"]["groundedness_pass"]
    )

    return {
        "total_questions": total_questions,
        "passed_questions": passed_questions,
        "pass_rate": round(pass_rate, 3),
        "questions_with_sources": questions_with_sources,
        "expected_regulation_found_count": expected_regulation_found,
        "top_source_matches_expected_count": top_source_matches,
        "average_keyword_coverage": round(average_keyword_coverage, 3),
        "average_faithfulness_score": round(average_faithfulness_score, 3),
        "groundedness_pass_count": groundedness_pass_count,
    }


# =============================================================================
# Save
# =============================================================================

def save_results(
    payload: dict[str, Any],
) -> None:
    """
    Save evaluation results to JSON.
    """

    EVALUATION_RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with EVALUATION_RESULTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Run full evaluation.
    """

    questions = load_evaluation_questions()
    openai_client = get_openai_client()

    results = [
        evaluate_single_question(
            item=item,
            openai_client=openai_client,
        )
        for item in questions
    ]

    summary = summarize_results(results)

    payload = {
        "evaluation_timestamp": datetime.now(UTC).isoformat(),
        "top_k": TOP_K,
        "summary": summary,
        "results": results,
    }

    save_results(payload)

    print("=" * 100)
    print("EVALUATION SUMMARY")
    print("=" * 100)
    print(json.dumps(summary, indent=2))
    print("=" * 100)
    print(f"Saved results to: {EVALUATION_RESULTS_PATH}")
    print("=" * 100)


if __name__ == "__main__":
    main()