"""
Bronze ingestion job for EU regulatory documents.

This script runs in Databricks as a Databricks Bundle job.

Input:
    Databricks Volume raw document files and manifest JSON.

Input Volume structure:
    /Volumes/<catalog>/<schema>/<volume>/
    ├── raw/
    │   ├── pdf/
    │   ├── html/
    │   └── xml/
    └── metadata/
        └── document_manifest.json
git 
Output:
    Bronze Delta tables:
    - bronze_regulatory_documents
    - bronze_document_pages

file: src/jobs/bronze_ingestion.py
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
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
# Make src/config.py importable when running from src/jobs in Databricks Bundle
# =============================================================================

def add_src_to_python_path() -> None:
    """
    Make src/config.py importable.

    In normal Python execution, __file__ exists.
    In some Databricks Bundle executions, __file__ is not defined because
    the task is executed through exec(...).

    This function supports both cases.
    """

    candidate_dirs = []

    try:
        current_file = Path(__file__).resolve()
        candidate_dirs.append(current_file.parents[1])
    except NameError:
        pass

    current_working_dir = Path.cwd()

    candidate_dirs.extend(
        [
            current_working_dir,
            current_working_dir / "src",
            current_working_dir / "files" / "src",
            current_working_dir.parent,
            current_working_dir.parent / "src",
            current_working_dir.parent / "files" / "src",
        ]
    )

    for candidate_dir in candidate_dirs:
        config_path = candidate_dir / "config.py"

        if config_path.exists():
            if str(candidate_dir) not in sys.path:
                sys.path.append(str(candidate_dir))

            print(f"Added to Python path: {candidate_dir}")
            return

    raise FileNotFoundError(
        "Could not find config.py. "
        f"Checked these folders: {[str(path) for path in candidate_dirs]}"
    )


add_src_to_python_path()

from config import (  # noqa: E402
    DATABRICKS_RAW_PDF_PATH,
    DATABRICKS_RAW_HTML_PATH,
    DATABRICKS_RAW_XML_PATH,
    DATABRICKS_DOCUMENT_MANIFEST_PATH,
    BRONZE_DOCUMENTS_TABLE,
    BRONZE_PAGES_TABLE,
)


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
        StructField("acquisition_method", StringType(), True),
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

    Bronze stays close to the original extracted content.
    More advanced cleaning belongs in Silver.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def infer_document_type(file_format: str | None, source_system: str | None) -> str | None:
    if file_format == "pdf":
        return "regulatory_document"

    if file_format == "html":
        return "regulatory_web_page"

    if file_format == "xml":
        return "api_xml_response"

    if source_system:
        return "external_source_document"

    return None


def infer_compliance_domain(category: str | None) -> str | None:
    if not category:
        return None

    mapping = {
        "Data Protection": "Data protection and privacy",
        "Digital Finance": "Digital operational resilience",
        "Payments": "Payment services",
        "Financial Markets": "Financial markets",
        "Artificial Intelligence": "AI governance",
        "Credit Risk": "Credit risk",
    }

    return mapping.get(category, category)


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize downloader manifest fields into the Bronze schema.

    The downloader manifest currently uses:
    - title
    - category
    - acquisition_method

    Bronze uses:
    - regulation_title
    - regulation_category
    - compliance_domain
    - document_type
    """

    title = record.get("regulation_title") or record.get("title")
    category = record.get("regulation_category") or record.get("category")
    file_format = record.get("file_format")
    source_system = record.get("source_system")

    normalized = {
        "document_id": record.get("document_id"),
        "celex": record.get("celex"),
        "short_title": record.get("short_title"),
        "regulation_title": title,
        "description": record.get("description"),
        "issuing_authority": record.get("issuing_authority") or source_system,
        "regulation_category": category,
        "compliance_domain": record.get("compliance_domain")
        or infer_compliance_domain(category),
        "document_type": record.get("document_type")
        or infer_document_type(file_format, source_system),
        "language": record.get("language") or "EN",
        "source_system": source_system,
        "source_url": record.get("source_url"),
        "file_format": file_format,
        "local_path": record.get("local_path"),
        "file_name": record.get("file_name"),
        "file_size_bytes": record.get("file_size_bytes"),
        "sha256": record.get("sha256"),
        "downloaded_at_utc": record.get("downloaded_at_utc"),
        "content_type": record.get("content_type"),
        "ingestion_status": record.get("ingestion_status"),
        "acquisition_method": record.get("acquisition_method"),
        "error": record.get("error"),
    }

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


def get_databricks_file_path(record: dict[str, Any]) -> str:
    """
    Build the Databricks Volume file path based on file format and file name.
    """

    file_format = record.get("file_format")
    file_name = record.get("file_name")

    if not file_name:
        raise ValueError(f"Missing file_name in manifest record: {record}")

    if file_format == "pdf":
        return f"{DATABRICKS_RAW_PDF_PATH}/{file_name}"

    if file_format == "html":
        return f"{DATABRICKS_RAW_HTML_PATH}/{file_name}"

    if file_format == "xml":
        return f"{DATABRICKS_RAW_XML_PATH}/{file_name}"

    raise ValueError(f"Unsupported file format: {file_format}")


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
    databricks_file_path = get_databricks_file_path(record)

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

    doc.close()

    return pages


# =============================================================================
# HTML extraction
# =============================================================================

def extract_html_sections(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract useful text from an HTML file.

    The EBA page contains a lot of navigation and menu HTML.
    This tries to keep the main article content when available.
    """

    file_name = record["file_name"]
    databricks_file_path = get_databricks_file_path(record)

    html_bytes = read_binary_file_with_spark(
        spark=spark,
        file_path=databricks_file_path,
    )

    html = html_bytes.decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()

    main_content = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", id="block-eba-theme-content")
        or soup.body
        or soup
    )

    text = clean_text(main_content.get_text(separator="\n"))

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

def extract_ecb_exchange_rates(xml_text: str) -> str:
    """
    Convert the ECB XML exchange-rate response into readable text.
    """

    try:
        root = ET.fromstring(xml_text)

        subject = None
        sender = None
        rate_date = None
        rates = []

        for element in root.iter():
            tag = element.tag.split("}")[-1]

            if tag == "subject" and element.text:
                subject = element.text.strip()

            if tag == "name" and element.text:
                sender = element.text.strip()

            if tag == "Cube":
                if "time" in element.attrib:
                    rate_date = element.attrib["time"]

                currency = element.attrib.get("currency")
                rate = element.attrib.get("rate")

                if currency and rate:
                    rates.append(f"{currency}: {rate}")

        lines = []

        if subject:
            lines.append(f"Subject: {subject}")

        if sender:
            lines.append(f"Sender: {sender}")

        if rate_date:
            lines.append(f"Date: {rate_date}")

        if rates:
            lines.append("Euro foreign exchange reference rates:")
            lines.extend(rates)

        if lines:
            return "\n".join(lines)

    except ET.ParseError:
        pass

    return ""


def extract_xml_sections(
    spark: SparkSession,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract text from an XML file.

    For the ECB XML source, this produces readable exchange-rate text.
    """

    file_name = record["file_name"]
    databricks_file_path = get_databricks_file_path(record)

    xml_bytes = read_binary_file_with_spark(
        spark=spark,
        file_path=databricks_file_path,
    )

    xml_text = xml_bytes.decode("utf-8", errors="ignore")

    text = extract_ecb_exchange_rates(xml_text)

    if not text:
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

    print(f"Reading manifest from: {DATABRICKS_DOCUMENT_MANIFEST_PATH}")

    manifest_records = load_manifest(
        spark=spark,
        manifest_path=DATABRICKS_DOCUMENT_MANIFEST_PATH,
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