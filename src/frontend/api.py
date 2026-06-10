"""
src/frontend/api.py

FastAPI backend for the Regulatory Compliance Assistant.

This API receives a user question, checks API key authentication,
redacts basic PII, calls the RAG service, and returns an answer with sources.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.governance.pii_redaction import redact_pii
from src.rag_service import answer_question


# =============================================================================
# Load environment variables
# =============================================================================

load_dotenv()


# =============================================================================
# Configuration
# =============================================================================

APP_API_KEY = os.getenv("APP_API_KEY", "demo-secret-key")


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
# Authentication helper
# =============================================================================

def validate_api_key(x_api_key: str | None) -> None:
    """
    Validate the API key sent by the frontend.

    The client must send:

        X-API-Key: demo-secret-key

    or whatever value is configured in APP_API_KEY.
    """

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key.",
        )

    if x_api_key != APP_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )


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
def ask(
    request: AskRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """
    Ask a regulatory compliance question.

    Security and governance steps:
    1. Validate API key.
    2. Redact common PII patterns.
    3. Send the redacted question to the RAG pipeline.
    """

    try:
        validate_api_key(x_api_key)

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

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )