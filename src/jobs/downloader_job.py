"""
src/jobs/downloader_job.py

Regulatory data downloader — runs as a Databricks job.

Downloads all documents automatically:
- EUR-Lex PDFs via CELLAR REST API (primary) or EUR-Lex direct URL (fallback)
- EBA HTML page
- ECB XML feed

Write strategy (Unity Catalog Volume POSIX limitations):
- PDFs (binary):    download → /tmp/ → dbutils.fs.cp() to Volume
- HTML/XML (text):  dbutils.fs.put() directly to Volume
- Manifest (JSON):  dbutils.fs.put() directly to Volume

Writes directly to:
- /Volumes/accenture2026dbcks/team4/volume/raw/pdf/
- /Volumes/accenture2026dbcks/team4/volume/raw/html/
- /Volumes/accenture2026dbcks/team4/volume/raw/xml/
- /Volumes/accenture2026dbcks/team4/volume/metadata/document_manifest.json
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import io

import requests
from databricks.sdk import WorkspaceClient


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"
VOLUME = "volume"

VOLUME_ROOT = Path(f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}")

RAW_DIR = VOLUME_ROOT / "raw"
PDF_DIR = RAW_DIR / "pdf"
HTML_DIR = RAW_DIR / "html"
XML_DIR = RAW_DIR / "xml"
METADATA_DIR = VOLUME_ROOT / "metadata"
MANIFEST_PATH = METADATA_DIR / "document_manifest.json"

REQUEST_TIMEOUT = 60
RATE_LIMIT_DELAY = 1.5


DOCUMENTS = [
    {
        "document_id": "32016R0679",
        "celex": "32016R0679",
        "short_title": "GDPR",
        "title": "General Data Protection Regulation",
        "category": "Data Protection",
        "source_system": "EUR-Lex",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32016R0679",
        "file_format": "pdf",
        "file_name": "32016R0679_GDPR_EN.pdf",
        "method": "download",
    },
    {
        "document_id": "32022R2554",
        "celex": "32022R2554",
        "short_title": "DORA",
        "title": "Digital Operational Resilience Act",
        "category": "Digital Finance",
        "source_system": "EUR-Lex",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32022R2554",
        "file_format": "pdf",
        "file_name": "32022R2554_DORA_EN.pdf",
        "method": "download",
    },
    {
        "document_id": "32015L2366",
        "celex": "32015L2366",
        "short_title": "PSD2",
        "title": "Payment Services Directive 2",
        "category": "Payments",
        "source_system": "EUR-Lex",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32015L2366",
        "file_format": "pdf",
        "file_name": "32015L2366_PSD2_EN.pdf",
        "method": "download",
    },
    {
        "document_id": "32014L0065",
        "celex": "32014L0065",
        "short_title": "MiFID_II",
        "title": "Markets in Financial Instruments Directive II",
        "category": "Financial Markets",
        "source_system": "EUR-Lex",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32014L0065",
        "file_format": "pdf",
        "file_name": "32014L0065_MiFID_II_EN.pdf",
        "method": "download",
    },
    {
        "document_id": "32024R1689",
        "celex": "32024R1689",
        "short_title": "AI_Act",
        "title": "Artificial Intelligence Act",
        "category": "Artificial Intelligence",
        "source_system": "EUR-Lex",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689",
        "file_format": "pdf",
        "file_name": "32024R1689_AI_Act_EN.pdf",
        "method": "download",
    },
    {
        "document_id": "eba_loan_origination_guidelines_html",
        "celex": None,
        "short_title": "EBA_Loan_Origination",
        "title": "EBA Guidelines on Loan Origination and Monitoring",
        "category": "Credit Risk",
        "source_system": "EBA",
        "source_url": (
            "https://www.eba.europa.eu/activities/single-rulebook/"
            "regulatory-activities/credit-risk/"
            "guidelines-loan-origination-and-monitoring"
        ),
        "file_format": "html",
        "file_name": "eba_loan_origination_guidelines_html.html",
        "method": "download",
    },
    {
        "document_id": "ecb_eurofxref_daily_xml",
        "celex": None,
        "short_title": "ECB_Exchange_Rates",
        "title": "ECB Euro Foreign Exchange Reference Rates",
        "category": "Financial Markets",
        "source_system": "ECB",
        "source_url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        "file_format": "xml",
        "file_name": "ecb_eurofxref_daily_xml.xml",
        "method": "download",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def output_dir_for(file_format: str) -> Path:
    if file_format == "pdf":
        return PDF_DIR
    if file_format == "html":
        return HTML_DIR
    if file_format == "xml":
        return XML_DIR
    raise ValueError(f"Unsupported file format: {file_format}")


def create_metadata(document: dict[str, Any], file_path: Path) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "celex": document.get("celex"),
        "short_title": document["short_title"],
        "title": document["title"],
        "category": document["category"],
        "language": "EN",
        "source_system": document["source_system"],
        "source_url": document["source_url"],
        "file_format": document["file_format"],
        "file_name": file_path.name,
        "volume_path": str(file_path),
        "file_size_bytes": None,   # skipped — POSIX reads not supported on this volume from jobs
        "sha256": None,            # skipped — same reason
        "downloaded_at_utc": now_utc(),
        "ingestion_status": "downloaded",
        "acquisition_method": "automatic_download",
    }


def create_failed_metadata(document: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "celex": document.get("celex"),
        "short_title": document["short_title"],
        "title": document["title"],
        "category": document["category"],
        "source_system": document["source_system"],
        "source_url": document["source_url"],
        "file_format": document["file_format"],
        "ingestion_status": "failed",
        "error": str(error),
        "downloaded_at_utc": now_utc(),
    }


def _extract_english_cellar_id(rdf_text: str) -> str:
    """
    Extract the CELLAR UUID.ExpressionNumber for the English expression.

    The RDF contains description blocks like:
        <rdf:Description rdf:about=".../cellar/{uuid}.{expr_num}">
            <j.2:lang>en</j.2:lang>
            <j.2:lang>eng</j.2:lang>
        </rdf:Description>

    We find the block with English language tags and extract uuid.expr_num.
    """
    blocks = rdf_text.split("<rdf:Description")
    for block in blocks:
        if ">en<" not in block and ">eng<" not in block:
            continue
        match = re.search(
            r'rdf:about="http://publications\.europa\.eu/resource/cellar/'
            r'([a-f0-9-]+\.\d+)"',
            block,
        )
        if match:
            return match.group(1)
    raise ValueError("Could not find English CELLAR expression identifier in RDF")


def download_pdf_bytes(document: dict[str, Any]) -> bytes:
    """
    Download a EUR-Lex PDF via CELLAR — two-step process:

    Step 1: Request RDF metadata for the CELEX ID to find the CELLAR
            UUID + English expression number (e.g. uuid.0006).
    Step 2: Download the PDF/A manifestation at {uuid}.{expr}.01/DOC_1.

    This works from Databricks cloud IPs where EUR-Lex direct URLs are blocked.
    """
    celex_id = document["celex"]

    # Step 1: fetch RDF to find the English CELLAR expression identifier
    rdf_response = requests.get(
        f"https://publications.europa.eu/resource/celex/{celex_id}",
        headers={
            "Accept": "application/rdf+xml",
            "Accept-Language": "eng",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=60,
        allow_redirects=True,
    )
    rdf_response.raise_for_status()

    cellar_id = _extract_english_cellar_id(rdf_response.text)
    print(f"[{celex_id}] CELLAR expression: {cellar_id}")

    # Step 2: download PDF/A from manifestation .01 / DOC_1
    time.sleep(1)  # be polite between the two requests
    pdf_url = f"https://publications.europa.eu/resource/cellar/{cellar_id}.01/DOC_1"
    pdf_response = requests.get(
        pdf_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=120,
        allow_redirects=True,
    )
    pdf_response.raise_for_status()

    content_type = pdf_response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower():
        raise ValueError(
            f"Expected PDF but got {content_type}. "
            f"URL: {pdf_url}"
        )

    print(f"[{celex_id}] Downloaded {len(pdf_response.content):,} bytes")
    return pdf_response.content


def download_file(document: dict[str, Any]) -> Path:
    """
    Download a document and write it to the Unity Catalog Volume.

    PDFs (binary):   CELLAR two-step download → SDK files.upload() to Volume.
    HTML/XML (text): requests.get() → dbutils.fs.put() to Volume.

    Spark Connect (serverless) does not support spark._jvm, so Hadoop FS is unavailable.
    SDK files.upload() handles binary and authenticates automatically from the job context.
    """
    file_format = document["file_format"]
    target_path = output_dir_for(file_format) / document["file_name"]

    if file_format == "pdf":
        pdf_bytes = download_pdf_bytes(document)
        WorkspaceClient().files.upload(
            file_path=str(target_path),
            contents=io.BytesIO(pdf_bytes),
            overwrite=True,
        )
        print(f"Uploaded {len(pdf_bytes):,} bytes via SDK")

    else:
        response = requests.get(
            document["source_url"],
            headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        dbutils.fs.put(str(target_path), response.text, overwrite=True)  # noqa: F821

    return target_path


def acquire_document(document: dict[str, Any]) -> dict[str, Any]:
    print(f"Processing: {document['short_title']}")
    file_path = download_file(document)
    print(f"Ready: {file_path}")
    return create_metadata(document, file_path)


def save_manifest(records: list[dict[str, Any]]) -> None:
    content = json.dumps(records, indent=4, ensure_ascii=False)
    dbutils.fs.put(str(MANIFEST_PATH), content, overwrite=True)  # noqa: F821
    print(f"Manifest saved to: {MANIFEST_PATH}")


def download_corpus() -> list[dict[str, Any]]:
    manifest = []
    for i, document in enumerate(DOCUMENTS):
        try:
            metadata = acquire_document(document)
        except Exception as error:
            print(f"Failed: {document['short_title']}")
            print(f"Reason: {error}")
            metadata = create_failed_metadata(document, error)
        manifest.append(metadata)
        print("-" * 80)
        if i < len(DOCUMENTS) - 1:
            time.sleep(RATE_LIMIT_DELAY)
    save_manifest(manifest)
    return manifest


if __name__ == "__main__":
    download_corpus()