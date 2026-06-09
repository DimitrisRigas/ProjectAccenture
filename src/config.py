"""
Central configuration for the AI-Powered Regulatory Compliance Assistant.

This file stores project settings in one place:
- local paths
- Databricks paths
- Delta table names
- RAG parameters
- Azure OpenAI settings

file: src/config.py
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()

except ModuleNotFoundError:
    pass


# =============================================================================
# Local project paths
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"

MANUAL_DATA_DIR = DATA_DIR / "manual"
MANUAL_PDF_DIR = MANUAL_DATA_DIR / "pdf"

LOCAL_PDF_DIR = RAW_DATA_DIR / "pdf"
LOCAL_HTML_DIR = RAW_DATA_DIR / "html"
LOCAL_XML_DIR = RAW_DATA_DIR / "xml"

LOCAL_DOCUMENT_MANIFEST_PATH = METADATA_DIR / "document_manifest.json"


# =============================================================================
# Databricks Unity Catalog configuration
# =============================================================================

DATABRICKS_CATALOG = os.getenv(
    "DATABRICKS_CATALOG",
    "accenture2026dbcks",
)

DATABRICKS_SCHEMA = os.getenv(
    "DATABRICKS_SCHEMA",
    "team4",
)

DATABRICKS_VOLUME = os.getenv(
    "DATABRICKS_VOLUME",
    "volume",
)


# =============================================================================
# Databricks Volume paths
# =============================================================================

DATABRICKS_VOLUME_PATH = (
    f"/Volumes/{DATABRICKS_CATALOG}/{DATABRICKS_SCHEMA}/{DATABRICKS_VOLUME}"
)

DATABRICKS_RAW_PATH = f"{DATABRICKS_VOLUME_PATH}/raw"

DATABRICKS_RAW_PDF_PATH = f"{DATABRICKS_RAW_PATH}/pdf"
DATABRICKS_RAW_HTML_PATH = f"{DATABRICKS_RAW_PATH}/html"
DATABRICKS_RAW_XML_PATH = f"{DATABRICKS_RAW_PATH}/xml"

DATABRICKS_METADATA_PATH = f"{DATABRICKS_VOLUME_PATH}/metadata"

DATABRICKS_DOCUMENT_MANIFEST_PATH = (
    f"{DATABRICKS_METADATA_PATH}/document_manifest.json"
)


# =============================================================================
# Delta table names
# =============================================================================

BRONZE_DOCUMENTS_TABLE = (
    f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.bronze_regulatory_documents"
)

BRONZE_PAGES_TABLE = (
    f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.bronze_document_pages"
)

SILVER_CHUNKS_TABLE = (
    f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.silver_document_chunks"
)

GOLD_EMBEDDINGS_TABLE = (
    f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.gold_document_embeddings"
)


# =============================================================================
# Local vector store settings
# =============================================================================

CHROMA_PATH = BASE_DIR / "chroma_db"

COLLECTION_NAME = os.getenv(
    "COLLECTION_NAME",
    "regulatory_compliance_collection",
)


# =============================================================================
# Chunking settings
# =============================================================================

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


# =============================================================================
# Retrieval settings
# =============================================================================

TOP_K = int(os.getenv("TOP_K", "5"))


# =============================================================================
# Embedding settings
# =============================================================================

LOCAL_EMBEDDING_MODEL_NAME = os.getenv(
    "LOCAL_EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)

DATABRICKS_EMBEDDING_ENDPOINT = os.getenv(
    "DATABRICKS_EMBEDDING_ENDPOINT",
    "databricks-gte-large-en",
)

EMBEDDING_VERSION = os.getenv(
    "EMBEDDING_VERSION",
    "v1",
)


# =============================================================================
# Azure OpenAI settings
# =============================================================================

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")


# =============================================================================
# FastAPI settings
# =============================================================================

API_TITLE = "AI-Powered Regulatory Compliance Assistant"

API_VERSION = "0.1.0"

API_DESCRIPTION = (
    "A RAG-based assistant for querying EU regulatory documents "
    "with grounded answers and source citations."
)


# =============================================================================
# Debug helper
# =============================================================================

def print_config() -> None:
    """
    Print non-secret configuration values for debugging.

    Do not print API keys or tokens.
    """

    print("Configuration")
    print("=" * 80)

    print(f"BASE_DIR: {BASE_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")

    print("-" * 80)

    print(f"RAW_DATA_DIR: {RAW_DATA_DIR}")
    print(f"METADATA_DIR: {METADATA_DIR}")
    print(f"MANUAL_DATA_DIR: {MANUAL_DATA_DIR}")
    print(f"MANUAL_PDF_DIR: {MANUAL_PDF_DIR}")

    print("-" * 80)

    print(f"LOCAL_PDF_DIR: {LOCAL_PDF_DIR}")
    print(f"LOCAL_HTML_DIR: {LOCAL_HTML_DIR}")
    print(f"LOCAL_XML_DIR: {LOCAL_XML_DIR}")
    print(f"LOCAL_DOCUMENT_MANIFEST_PATH: {LOCAL_DOCUMENT_MANIFEST_PATH}")

    print("-" * 80)

    print(f"DATABRICKS_CATALOG: {DATABRICKS_CATALOG}")
    print(f"DATABRICKS_SCHEMA: {DATABRICKS_SCHEMA}")
    print(f"DATABRICKS_VOLUME: {DATABRICKS_VOLUME}")
    print(f"DATABRICKS_VOLUME_PATH: {DATABRICKS_VOLUME_PATH}")

    print("-" * 80)

    print(f"DATABRICKS_RAW_PATH: {DATABRICKS_RAW_PATH}")
    print(f"DATABRICKS_RAW_PDF_PATH: {DATABRICKS_RAW_PDF_PATH}")
    print(f"DATABRICKS_RAW_HTML_PATH: {DATABRICKS_RAW_HTML_PATH}")
    print(f"DATABRICKS_RAW_XML_PATH: {DATABRICKS_RAW_XML_PATH}")
    print(f"DATABRICKS_METADATA_PATH: {DATABRICKS_METADATA_PATH}")
    print(f"DATABRICKS_DOCUMENT_MANIFEST_PATH: {DATABRICKS_DOCUMENT_MANIFEST_PATH}")

    print("-" * 80)

    print(f"BRONZE_DOCUMENTS_TABLE: {BRONZE_DOCUMENTS_TABLE}")
    print(f"BRONZE_PAGES_TABLE: {BRONZE_PAGES_TABLE}")
    print(f"SILVER_CHUNKS_TABLE: {SILVER_CHUNKS_TABLE}")
    print(f"GOLD_EMBEDDINGS_TABLE: {GOLD_EMBEDDINGS_TABLE}")

    print("-" * 80)

    print(f"CHROMA_PATH: {CHROMA_PATH}")
    print(f"COLLECTION_NAME: {COLLECTION_NAME}")

    print("-" * 80)

    print(f"CHUNK_SIZE: {CHUNK_SIZE}")
    print(f"CHUNK_OVERLAP: {CHUNK_OVERLAP}")
    print(f"TOP_K: {TOP_K}")

    print("-" * 80)

    print(f"LOCAL_EMBEDDING_MODEL_NAME: {LOCAL_EMBEDDING_MODEL_NAME}")
    print(f"DATABRICKS_EMBEDDING_ENDPOINT: {DATABRICKS_EMBEDDING_ENDPOINT}")
    print(f"EMBEDDING_VERSION: {EMBEDDING_VERSION}")

    print("=" * 80)


if __name__ == "__main__":
    print_config()