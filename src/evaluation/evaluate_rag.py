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

Output:
    evaluation/evaluation_results.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.rag_service import answer_question


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EVALUATION_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "evaluation_questions.json"
EVALUATION_RESULTS_PATH = PROJECT_ROOT / "evaluation" / "evaluation_results.json"

TOP_K = 5


def load_evaluation_questions() -> list[dict[str, Any]]:
    """
    Load evaluation questions from JSON.
    """

    with EVALUATION_QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(value: str | None) -> str:
    """
    Normalize text for simple comparisons.
    """

    if value is None:
        return ""

    return value.lower().replace("-", " ").replace("_", " ").strip()


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


def evaluate_single_question(
    item: dict[str, Any],
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

    passed = (
        has_sources
        and regulation_check["expected_regulation_found"]
        and keyword_check["keyword_coverage"] >= 0.4
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
        "answer_preview": answer[:700],
    }

    print(f"Passed: {passed}")
    print(f"Expected regulation found: {regulation_check['expected_regulation_found']}")
    print(f"Keyword coverage: {keyword_check['keyword_coverage']}")
    print(f"Number of sources: {len(sources)}")
    print()

    return evaluation_result


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

    return {
        "total_questions": total_questions,
        "passed_questions": passed_questions,
        "pass_rate": round(pass_rate, 3),
        "questions_with_sources": questions_with_sources,
        "expected_regulation_found_count": expected_regulation_found,
        "top_source_matches_expected_count": top_source_matches,
        "average_keyword_coverage": round(average_keyword_coverage, 3),
    }


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


def main() -> None:
    """
    Run full evaluation.
    """

    questions = load_evaluation_questions()

    results = [
        evaluate_single_question(item)
        for item in questions
    ]

    summary = summarize_results(results)

    payload = {
        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
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