"""
src/frontend/api.py

FastAPI backend for the Regulatory Compliance Assistant.

This API receives a user question, redacts basic PII, calls the RAG service,
and returns an answer with sources.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.governance.pii_redaction import redact_pii
from src.rag_service import answer_question


# =============================================================================
# FastAPI app
# =============================================================================

app = FastAPI(
    title="Regulatory Compliance Assistant API",
    description="RAG API for EU financial regulatory compliance documents.",
    version="1.0.0",
)


# =============================================================================
# CORS
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request / response models
# =============================================================================

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="The user's regulatory compliance question.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve from Azure AI Search.",
    )


class Source(BaseModel):
    source_number: int
    chunk_id: str | None = None
    short_title: str | None = None
    regulation_title: str | None = None
    source_url: str | None = None
    page_number: int | None = None
    file_name: str | None = None
    score: float | None = None
    chunk_preview: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]


# =============================================================================
# Routes
# =============================================================================

@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Regulatory Compliance Assistant API is running."
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok"
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict[str, Any]:
    """
    Ask a regulatory compliance question.

    Before the question is sent to the RAG pipeline, common PII patterns
    are redacted. This adds a lightweight governance control.
    """

    try:
        redaction_result = redact_pii(request.question)

        print("=" * 100)
        print("PII REDACTION")
        print("=" * 100)
        print("Original question:")
        print(request.question)
        print()
        print("Redacted question:")
        print(redaction_result.redacted_text)
        print()
        print("Redactions:")
        print(redaction_result.redactions)
        print("=" * 100)

        result = answer_question(
            question=redaction_result.redacted_text,
            top_k=request.top_k,
        )

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )