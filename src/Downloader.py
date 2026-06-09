"""
src/downloader.py

Simplified regulatory data downloader.

Downloads / registers:
- EUR-Lex PDFs from manual browser-downloaded files in data/manual/pdf/
- 1 HTML regulatory page from EBA
- 1 XML API file from ECB

Creates:
- data/raw/pdf/
- data/raw/html/
- data/raw/xml/
- data/metadata/document_manifest.json

The manual EUR-Lex safeguard is kept because EUR-Lex may block automated downloads.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


# Because this file is located at:
# ProjectAccenture/src/downloader.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_PDF_DIR = DATA_DIR / "manual" / "pdf"

PDF_DIR = RAW_DIR / "pdf"
HTML_DIR = RAW_DIR / "html"
XML_DIR = RAW_DIR / "xml"

METADATA_DIR = DATA_DIR / "metadata"
MANIFEST_PATH = METADATA_DIR / "document_manifest.json"


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
        "method": "manual",
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
        "method": "manual",
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
        "method": "manual",
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
        "method": "manual",
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
        "method": "manual",
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


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def validate_file(path: Path, file_format: str) -> None:
    content = path.read_bytes().lstrip()

    if file_format == "pdf" and not content.startswith(b"%PDF"):
        raise ValueError(f"Invalid PDF file: {path}")

    if file_format == "html" and b"<html" not in content[:2000].lower():
        raise ValueError(f"Invalid HTML file: {path}")

    if file_format == "xml" and not content.startswith(b"<?xml"):
        raise ValueError(f"Invalid XML file: {path}")


def output_dir_for(file_format: str) -> Path:
    if file_format == "pdf":
        return PDF_DIR

    if file_format == "html":
        return HTML_DIR

    if file_format == "xml":
        return XML_DIR

    raise ValueError(f"Unsupported file format: {file_format}")


def create_metadata(document: dict[str, Any], file_path: Path) -> dict[str, Any]:
    acquisition_method = (
        "manual_browser_download"
        if document["method"] == "manual"
        else "automatic_download"
    )

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
        "local_path": str(file_path),
        "file_size_bytes": file_path.stat().st_size,
        "sha256": sha256_file(file_path),
        "downloaded_at_utc": now_utc(),
        "ingestion_status": "downloaded",
        "acquisition_method": acquisition_method,
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


def register_manual_pdf(document: dict[str, Any]) -> Path:
    """
    Register a manually downloaded EUR-Lex PDF.

    Expected input:
        data/manual/pdf/<file_name>

    Output copy:
        data/raw/pdf/<file_name>
    """

    MANUAL_PDF_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    source_path = MANUAL_PDF_DIR / document["file_name"]
    target_path = PDF_DIR / document["file_name"]

    if not source_path.exists():
        raise FileNotFoundError(
            f"Manual PDF not found: {source_path}\n"
            f"Download it manually from:\n{document['source_url']}"
        )

    validate_file(source_path, "pdf")

    shutil.copy2(source_path, target_path)

    return target_path


def download_file(document: dict[str, Any]) -> Path:
    target_dir = output_dir_for(document["file_format"])
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / document["file_name"]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }

    response = requests.get(
        document["source_url"],
        headers=headers,
        timeout=60,
        allow_redirects=True,
    )
    response.raise_for_status()

    target_path.write_bytes(response.content)

    validate_file(target_path, document["file_format"])

    return target_path


def acquire_document(document: dict[str, Any]) -> dict[str, Any]:
    print(f"Processing: {document['short_title']}")

    if document["method"] == "manual":
        file_path = register_manual_pdf(document)
    elif document["method"] == "download":
        file_path = download_file(document)
    else:
        raise ValueError(f"Unknown acquisition method: {document['method']}")

    print(f"Saved: {file_path}")

    return create_metadata(document, file_path)


def save_manifest(records: list[dict[str, Any]]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    with MANIFEST_PATH.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=4, ensure_ascii=False)

    print(f"Manifest saved to: {MANIFEST_PATH}")


def download_corpus() -> list[dict[str, Any]]:
    manifest = []

    for document in DOCUMENTS:
        try:
            metadata = acquire_document(document)
        except Exception as error:
            print(f"Failed: {document['short_title']}")
            print(f"Reason: {error}")
            metadata = create_failed_metadata(document, error)

        manifest.append(metadata)
        print("-" * 80)

    save_manifest(manifest)

    return manifest


if __name__ == "__main__":
    download_corpus()