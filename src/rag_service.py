"""
src/rag_service.py

Local RAG service using:

- Azure OpenAI GPT-4o for answer generation
- Azure OpenAI text-embedding-3-small for query embeddings
- Azure AI Search for hybrid retrieval

Hybrid retrieval means:
- keyword search over chunk_text
- vector search over embedding

Expected Azure AI Search index fields:
- chunk_id
- chunk_text
- embedding
- short_title
- regulation_title
- source_url
- page_number
- file_name
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import AzureOpenAI

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery


# =============================================================================
# Load .env
# =============================================================================

load_dotenv()


# =============================================================================
# Environment variables
# =============================================================================

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

AI_SEARCH_ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
AI_SEARCH_API_KEY = os.getenv("AI_SEARCH_API_KEY")
AI_SEARCH_INDEX_NAME = os.getenv("AI_SEARCH_INDEX_NAME")

AI_SEARCH_VECTOR_FIELD = os.getenv("AI_SEARCH_VECTOR_FIELD", "embedding")
AI_SEARCH_CONTENT_FIELD = os.getenv("AI_SEARCH_CONTENT_FIELD", "chunk_text")

TOP_K = int(os.getenv("TOP_K", "5"))


# =============================================================================
# Environment validation
# =============================================================================

REQUIRED_ENV_VARS = {
    "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
    "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
    "AZURE_OPENAI_DEPLOYMENT_NAME": AZURE_OPENAI_DEPLOYMENT_NAME,
    "EMBEDDING_MODEL_NAME": EMBEDDING_MODEL_NAME,
    "AI_SEARCH_ENDPOINT": AI_SEARCH_ENDPOINT,
    "AI_SEARCH_API_KEY": AI_SEARCH_API_KEY,
    "AI_SEARCH_INDEX_NAME": AI_SEARCH_INDEX_NAME,
}


def validate_environment() -> None:
    """
    Check that all required .env variables exist.
    """

    missing = [
        name
        for name, value in REQUIRED_ENV_VARS.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing required environment variables:\n"
            + "\n".join(f"- {name}" for name in missing)
        )


# =============================================================================
# Clients
# =============================================================================

def get_openai_client() -> AzureOpenAI:
    """
    Create Azure OpenAI client.
    """

    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def get_search_client() -> SearchClient:
    """
    Create Azure AI Search client.
    """

    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AI_SEARCH_API_KEY),
    )


# =============================================================================
# Data model
# =============================================================================

@dataclass
class RetrievedChunk:
    chunk_id: str | None
    chunk_text: str
    short_title: str | None
    regulation_title: str | None
    source_url: str | None
    page_number: int | None
    file_name: str | None
    score: float | None


# =============================================================================
# Embeddings
# =============================================================================

def embed_query(
    client: AzureOpenAI,
    query: str,
) -> list[float]:
    """
    Create an embedding for the user's question.
    """

    response = client.embeddings.create(
        model=EMBEDDING_MODEL_NAME,
        input=query,
    )

    return response.data[0].embedding


# =============================================================================
# Retrieval
# =============================================================================

def search_relevant_chunks(
    search_client: SearchClient,
    query: str,
    query_embedding: list[float],
    top_k: int = TOP_K,
) -> list[RetrievedChunk]:
    """
    Search Azure AI Search using hybrid retrieval.

    Hybrid search combines:
    - keyword search over chunk_text
    - vector similarity search over embedding

    This improves retrieval when the user mentions exact regulation names
    such as GDPR, DORA, PSD2, MiFID II, or AI Act.
    """

    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k,
        fields=AI_SEARCH_VECTOR_FIELD,
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        select=[
            "chunk_id",
            AI_SEARCH_CONTENT_FIELD,
            "short_title",
            "regulation_title",
            "source_url",
            "page_number",
            "file_name",
        ],
        top=top_k,
    )

    chunks = []

    for result in results:
        chunks.append(
            RetrievedChunk(
                chunk_id=result.get("chunk_id"),
                chunk_text=result.get(AI_SEARCH_CONTENT_FIELD, ""),
                short_title=result.get("short_title"),
                regulation_title=result.get("regulation_title"),
                source_url=result.get("source_url"),
                page_number=result.get("page_number"),
                file_name=result.get("file_name"),
                score=result.get("@search.score"),
            )
        )

    return chunks


# =============================================================================
# Prompt building
# =============================================================================

def build_context(chunks: list[RetrievedChunk]) -> str:
    """
    Convert retrieved chunks into a context block for GPT-4o.
    """

    context_parts = []

    for index, chunk in enumerate(chunks, start=1):
        page = (
            str(chunk.page_number)
            if chunk.page_number is not None
            else "unknown"
        )

        context_parts.append(
            f"[Source {index}]\n"
            f"Chunk ID: {chunk.chunk_id or 'N/A'}\n"
            f"Short title: {chunk.short_title or 'N/A'}\n"
            f"Regulation title: {chunk.regulation_title or 'N/A'}\n"
            f"File name: {chunk.file_name or 'N/A'}\n"
            f"Page number: {page}\n"
            f"Source URL: {chunk.source_url or 'N/A'}\n"
            f"Search score: {chunk.score}\n"
            f"Text:\n{chunk.chunk_text}"
        )

    return "\n\n".join(context_parts)


def build_messages(question: str, context: str) -> list[dict[str, str]]:
    """
    Build the system and user messages for GPT-4o.
    """

    system_message = """
You are an AI-powered regulatory compliance assistant for EU financial institutions.

Your task is to answer user questions using ONLY the retrieved regulatory context provided to you.

You must follow these rules:

1. Grounding and citations
- Use only the retrieved context.
- Do not use outside knowledge, even if you know the answer.
- Every important legal, regulatory, or compliance claim must be supported by a source citation such as [Source 1] or [Source 2].
- If the context includes page numbers, mention them naturally when useful.
- Do not cite a source unless it actually supports the statement.

2. No hallucination
- Do not invent article numbers, deadlines, penalties, obligations, definitions, or legal interpretations.
- If the retrieved context is insufficient, clearly say:
  "The retrieved documents do not contain enough information to answer this fully."
- If only partial information is available, answer only the supported part and explain what is missing.

3. Compliance style
- Write in a clear, professional tone suitable for compliance officers, auditors, legal teams, and risk managers.
- Prefer practical language over vague legal wording.
- Distinguish between obligations, recommendations, definitions, and context when possible.
- Do not provide legal advice. Provide an informational regulatory summary based on the retrieved documents.

4. Answer structure
When appropriate, structure the answer as:
- Short direct answer
- Key obligations / requirements
- Practical compliance interpretation
- Sources used

5. Source awareness
- Pay attention to the regulation title, short title, file name, page number, and source URL in the retrieved context.
- If the user asks about a specific regulation, prioritize sources from that regulation.
- If retrieved sources come from mixed regulations, explain only what is supported and avoid mixing unrelated frameworks.

6. Uncertainty
- If retrieved sources appear weak, incomplete, or unrelated, say so.
- Never make the answer sound more certain than the retrieved evidence allows.
"""

    user_message = f"""
User question:
{question}

Retrieved regulatory context:
{context}

Now answer the question using only the retrieved context.
"""

    return [
        {
            "role": "system",
            "content": system_message.strip(),
        },
        {
            "role": "user",
            "content": user_message.strip(),
        },
    ]
# =============================================================================
# Generation
# =============================================================================

def generate_answer(
    client: AzureOpenAI,
    question: str,
    chunks: list[RetrievedChunk],
) -> str:
    """
    Generate the final answer using GPT-4o.
    """

    context = build_context(chunks)
    messages = build_messages(question, context)

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=messages,
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


# =============================================================================
# Public RAG function
# =============================================================================

def answer_question(
    question: str,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """
    Full RAG pipeline:

    1. Validate environment
    2. Embed question
    3. Retrieve relevant chunks from Azure AI Search using hybrid search
    4. Generate grounded answer with GPT-4o
    """

    validate_environment()

    openai_client = get_openai_client()
    search_client = get_search_client()

    query_embedding = embed_query(
        client=openai_client,
        query=question,
    )

    chunks = search_relevant_chunks(
        search_client=search_client,
        query=question,
        query_embedding=query_embedding,
        top_k=top_k,
    )

    if not chunks:
        return {
            "question": question,
            "answer": "I could not find relevant information in the Azure AI Search index.",
            "sources": [],
        }

    answer = generate_answer(
        client=openai_client,
        question=question,
        chunks=chunks,
    )

    sources = [
        {
            "source_number": index,
            "chunk_id": chunk.chunk_id,
            "short_title": chunk.short_title,
            "regulation_title": chunk.regulation_title,
            "source_url": chunk.source_url,
            "page_number": chunk.page_number,
            "file_name": chunk.file_name,
            "score": chunk.score,
            "chunk_preview": chunk.chunk_text[:1200],
        }
        for index, chunk in enumerate(chunks, start=1)
    ]

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }


# =============================================================================
# Manual test
# =============================================================================

if __name__ == "__main__":
    test_question = (
        "According to GDPR, what obligations do controllers have "
        "for personal data protection?"
    )

    result = answer_question(
        question=test_question,
        top_k=5,
    )

    print("=" * 100)
    print("QUESTION")
    print("=" * 100)
    print(result["question"])

    print("=" * 100)
    print("ANSWER")
    print("=" * 100)
    print(result["answer"])

    print("=" * 100)
    print("SOURCES")
    print("=" * 100)

    for source in result["sources"]:
        print(f"Source {source['source_number']}")
        print(f"Chunk ID: {source['chunk_id']}")
        print(f"Short title: {source['short_title']}")
        print(f"Regulation title: {source['regulation_title']}")
        print(f"File name: {source['file_name']}")
        print(f"Page number: {source['page_number']}")
        print(f"Source URL: {source['source_url']}")
        print(f"Score: {source['score']}")
        print("Preview:")
        print(source["chunk_preview"])
        print("-" * 100)