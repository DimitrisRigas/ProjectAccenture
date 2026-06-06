"""
Bronze ingestion job for EU regulatory documents.

This script runs in Databricks as a Databricks Bundle job.

Input:
    /Volumes/accenture2026dbcks/team4/volume/raw/pdf
    /Volumes/accenture2026dbcks/team4/volume/raw/html
    /Volumes/accenture2026dbcks/team4/volume/raw/xml
    /Volumes/accenture2026dbcks/team4/volume/metadata/document_manifest.json

Output:
    accenture2026dbcks.team4.bronze_regulatory_documents
    accenture2026dbcks.team4.bronze_document_pages
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import fitz
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    IntegerType,
)


# =============================================================================
# Databricks configuration
# =============================================================================

CATALOG = "accenture2026dbcks"
SCHEMA = "team4"
VOLUME = "volume"

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

RAW_PDF_PATH = f"{VOLUME_PATH}/raw/pdf"
RAW_HTML_PATH = f"{VOLUME_PATH}/raw/html"
RAW_XML_PATH = f"{VOLUME_PATH}/raw/xml"
MANIFEST_PATH = f"{VOLUME_PATH}/metadata/document_manifest.json"

BRONZE_DOCUMENTS_TABLE = f"{CATALOG}.{SCHEMA}.bronze_regulatory_documents"
BRONZE_PAGES_TABLE = f"{CATALOG}.{SCHEMA}.bronze_document_pages"


# =============================================================================
# Explicit schemas
# =============================================================================

BRONZE_DOCUMENTS_SCHEMA = StructType(
    [
        StructField("document_id", StringType(), True),
        StructField("celex", StringType(), True),
        StructField("short_title", StringType(), True),
        StructField("regulation_title", StringType(), True),
        StructField("description", StringType(), True),
        StructField("issuing_authority", StringType(), True),
        StructField("regulation_category", StringType(), True),
        StructField("compliance_domain", StringType(), True),
        StructField("document_type", StringType(), True),
        StructField("language", StringType(), True),
        StructField("source_system", StringType(), True),
        StructField("source_url", StringType(), True),
        StructField("file_format", StringType(), True),
        StructField("local_path", StringType(), True),
        StructField("file_name", StringType(), True),
        StructField("file_size_bytes", LongType(), True),
        StructField("sha256", StringType(), True),
        StructField("downloaded_at_utc", StringType(), True),
        StructField("content_type", StringType(), True),
        StructField("ingestion_status", StringType(), True),
        StructField("error", StringType(), True),
    ]
)


BRONZE_PAGES_SCHEMA = StructType(
    [
        StructField("document_id", StringType(), True),
        StructField("celex", StringType(), True),
        StructField("short_title", StringType(), True),
        StructField("regulation_title", StringType(), True),
        StructField("regulation_category", StringType(), True),
        StructField("compliance_domain", StringType(), True),
        StructField("document_type", StringType(), True),
        StructField("language", StringType(), True),
        StructField("source_system", StringType(), True),
        StructField("source_url", StringType(), True),
        StructField("file_format", StringType(), True),
        StructField("source_file", StringType(), True),
        StructField("file_name", StringType(), True),
        StructField("page_number", IntegerType(), True),
        StructField("section_number", IntegerType(), True),
        StructField("text", StringType(), True),
        StructField("extracted_at_utc", StringType(), True),
    ]
)


# =============================================================================
# Helpers
# =============================================================================

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(text: str) -> str:
    """
    Basic Bronze-level text cleaning.
    Keep it light. More transformations belong in Silver.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure optional manifest fields exist so Spark schema creation does not fail.
    """

    defaults = {
        "document_id": None,
        "celex": None,
        "short_title": None,
        "regulation_title": None,
        "description": None,
        "issuing_authority": None,
        "regulation_category": None,
        "compliance_domain": None,
        "document_type": None,
        "language": None,
        "source_system": None,
        "source_url": None,
        "file_format": None,
        "local_path": None,
        "file_name": None,
        "file_size_bytes": None,
        "sha256": None,
        "downloaded_at_utc": None,
        "content_type": None,
        "ingestion_status": None,
        "error": None,
    }

    normalized = defaults.copy()
    normalized.update(record)

    return normalized


def load_manifest(
    spark: SparkSession,
    manifest_path: str,
) -> list[dict[str, Any]]:
    """
    Load manifest JSON from Databricks Volume using Spark.

    This avoids Python open() problems on /Volumes in serverless jobs.
    """

    df = (
        spark.read
        .option("multiLine", "true")
        .json(manifest_path)
    )

    records = [row.asDict(recursive=True) for row in df.collect()]

    return [normalize_record(record) for record in records]


def get_successful_manifest_records(
    manifest_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Keep only records that were downloaded successfully.
    """

    return [
        record
        for record in manifest_records
        if record.get("ingestion_status") == "downloaded"
    ]


def read_binary_file_with_spark(
    spark: SparkSession,
    file_path: str,
) -> bytes:
    """
    Read a file from Databricks Volume using Spark binaryFile.

    This is safer than direct Python open() for serverless Databricks jobs.
    """

    df = (
        spark.read
        .format("binaryFile")
        .load(file_path)
        .select("content")
    )

    row = df.first()

    if row is None:
        raise FileNotFoundError(f"File not found or unreadable: {file_path}")

    return bytes(row["content"])


def get_required_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """
    Extract metadata fields reused by all document formats.
    """

    return {
        "document_id": record.get("document_id"),
        "celex": record.get("celex"),
        "short_title": record.get("short_title"),
        "regulation_title": record.get("regulation_title"),
        "regulation_category": record.get("regulation_category"),
        "compliance_domain": record.get("compliance_domain"),
        "document_type": record.get("document_type"),
        "language": record.get("language"),
        "source_system": record.get("source_system"),
        "source_url": record.get("source_url"),
    }


# =============================================================================
# PDF extraction
# =============================================================================

def extract_pdf_pages(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract text from a PDF file page by page.
    """

    file_name = record["file_name"]
    databricks_file_path = f"{RAW_PDF_PATH}/{file_name}"

    pdf_bytes = read_binary_file_with_spark(
        spark=spark,
        file_path=databricks_file_path,
    )

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    pages = []
    metadata = get_required_metadata(record)

    for page_number, page in enumerate(doc, start=1):
        text = clean_text(page.get_text("text"))

        if not text:
            continue

        pages.append(
            {
                **metadata,
                "file_format": "pdf",
                "source_file": databricks_file_path,
                "file_name": file_name,
                "page_number": int(page_number),
                "section_number": None,
                "text": text,
                "extracted_at_utc": now_utc(),
            }
        )

    return pages


# =============================================================================
# HTML extraction
# =============================================================================

def extract_html_sections(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract text from an HTML file.
    """

    file_name = record["file_name"]
    databricks_file_path = f"{RAW_HTML_PATH}/{file_name}"

    html_bytes = read_binary_file_with_spark(
        spark=spark,
        file_path=databricks_file_path,
    )

    html = html_bytes.decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = clean_text(soup.get_text(separator="\n"))

    if not text:
        return []

    metadata = get_required_metadata(record)

    return [
        {
            **metadata,
            "file_format": "html",
            "source_file": databricks_file_path,
            "file_name": file_name,
            "page_number": None,
            "section_number": 1,
            "text": text,
            "extracted_at_utc": now_utc(),
        }
    ]


# =============================================================================
# XML extraction
# =============================================================================

def extract_xml_sections(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract text from an XML file.
    """

    file_name = record["file_name"]
    databricks_file_path = f"{RAW_XML_PATH}/{file_name}"

    xml_bytes = read_binary_file_with_spark(
        spark=spark,
        file_path=databricks_file_path,
    )

    xml_text = xml_bytes.decode("utf-8", errors="ignore")

    text_without_tags = re.sub(r"<[^>]+>", " ", xml_text)
    text = clean_text(text_without_tags)

    if not text:
        return []

    metadata = get_required_metadata(record)

    return [
        {
            **metadata,
            "file_format": "xml",
            "source_file": databricks_file_path,
            "file_name": file_name,
            "page_number": None,
            "section_number": 1,
            "text": text,
            "extracted_at_utc": now_utc(),
        }
    ]


# =============================================================================
# Extraction router
# =============================================================================

def extract_document_text(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Route extraction based on file format.
    """

    file_format = record.get("file_format")

    if file_format == "pdf":
        return extract_pdf_pages(
            spark=spark,
            record=record,
        )

    if file_format == "html":
        return extract_html_sections(
            spark=spark,
            record=record,
        )

    if file_format == "xml":
        return extract_xml_sections(
            spark=spark,
            record=record,
        )

    print(f"Skipping unsupported file format: {file_format}")
    return []


# =============================================================================
# Table writers
# =============================================================================

def create_bronze_documents_table(
    spark: SparkSession,
    manifest_records: list[dict[str, Any]],
) -> None:
    """
    Save manifest records as Bronze document metadata table.
    """

    if not manifest_records:
        raise ValueError("Manifest contains no records.")

    normalized_records = [
        normalize_record(record)
        for record in manifest_records
    ]

    df = spark.createDataFrame(
        normalized_records,
        schema=BRONZE_DOCUMENTS_SCHEMA,
    )

    (
        df.withColumn("bronze_loaded_at", F.current_timestamp())
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(BRONZE_DOCUMENTS_TABLE)
    )

    print(f"Created table: {BRONZE_DOCUMENTS_TABLE}")
    print(f"Rows: {df.count()}")


def create_bronze_pages_table(
    spark: SparkSession,
    extracted_rows: list[dict[str, Any]],
) -> None:
    """
    Save extracted document text as Bronze pages table.
    """

    if not extracted_rows:
        raise ValueError("No extracted text rows found. Bronze pages table was not created.")

    df = spark.createDataFrame(
        extracted_rows,
        schema=BRONZE_PAGES_SCHEMA,
    )

    (
        df.withColumn("bronze_loaded_at", F.current_timestamp())
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(BRONZE_PAGES_TABLE)
    )

    print(f"Created table: {BRONZE_PAGES_TABLE}")
    print(f"Rows: {df.count()}")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    print("Starting Bronze ingestion")
    print("=" * 80)

    print(f"Reading manifest from: {MANIFEST_PATH}")

    manifest_records = load_manifest(
        spark=spark,
        manifest_path=MANIFEST_PATH,
    )

    successful_records = get_successful_manifest_records(manifest_records)

    print(f"Total manifest records: {len(manifest_records)}")
    print(f"Successful records: {len(successful_records)}")

    create_bronze_documents_table(
        spark=spark,
        manifest_records=manifest_records,
    )

    extracted_rows = []

    for record in successful_records:
        try:
            print(
                f"Extracting {record.get('short_title')} "
                f"as {record.get('file_format')} "
                f"from {record.get('file_name')}"
            )

            rows = extract_document_text(
                spark=spark,
                record=record,
            )

            extracted_rows.extend(rows)

            print(f"Extracted rows: {len(rows)}")
            print("-" * 80)

        except Exception as error:
            print(
                f"Failed to extract {record.get('short_title')} "
                f"{record.get('file_format')}: {error}"
            )
            print("-" * 80)

    create_bronze_pages_table(
        spark=spark,
        extracted_rows=extracted_rows,
    )

    print("=" * 80)
    print("Bronze ingestion completed.")


if __name__ == "__main__":
    main()