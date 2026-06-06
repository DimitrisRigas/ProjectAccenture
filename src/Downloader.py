"""
Download selected EU regulatory documents from EUR-Lex.

This script supports multiple document formats, not only PDFs.

Supported formats in this first version:
- PDF
- HTML
- XML

Project step:
    6.4 Data Ingestion & Regulatory Data Acquisition

The script also creates a metadata manifest for traceability,
lineage, and later loading into Databricks Delta tables.

file: ex1_download_documents.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


RAW_DATA_DIR = Path("data") / "raw"
METADATA_DIR = Path("data") / "metadata"
MANIFEST_PATH = METADATA_DIR / "document_manifest.json"


SUPPORTED_FORMATS = {"pdf", "html", "xml"}


EU_REGULATORY_DOCUMENTS: list[dict[str, Any]] = [
    {
        "document_id": "32016R0679",
        "celex": "32016R0679",
        "short_title": "GDPR",
        "regulation_title": "General Data Protection Regulation",
        "description": "Regulation on data protection and privacy in the European Union.",
        "issuing_authority": "European Parliament and Council of the European Union",
        "regulation_category": "Data Protection",
        "compliance_domain": "Privacy and Data Governance",
        "document_type": "Regulation",
        "language": "EN",
        "formats": ["pdf", "html", "xml"],
    },
    {
        "document_id": "32022R2554",
        "celex": "32022R2554",
        "short_title": "DORA",
        "regulation_title": "Digital Operational Resilience Act",
        "description": "Regulation on digital operational resilience for the financial sector.",
        "issuing_authority": "European Parliament and Council of the European Union",
        "regulation_category": "Digital Finance",
        "compliance_domain": "ICT Risk Management",
        "document_type": "Regulation",
        "language": "EN",
        "formats": ["pdf", "html", "xml"],
    },
    {
        "document_id": "32015L2366",
        "celex": "32015L2366",
        "short_title": "PSD2",
        "regulation_title": "Payment Services Directive 2",
        "description": "Directive on payment services in the internal market.",
        "issuing_authority": "European Parliament and Council of the European Union",
        "regulation_category": "Payments",
        "compliance_domain": "Banking and Payment Services",
        "document_type": "Directive",
        "language": "EN",
        "formats": ["pdf", "html", "xml"],
    },
    {
        "document_id": "32014L0065",
        "celex": "32014L0065",
        "short_title": "MiFID_II",
        "regulation_title": "Markets in Financial Instruments Directive II",
        "description": "Directive on markets in financial instruments.",
        "issuing_authority": "European Parliament and Council of the European Union",
        "regulation_category": "Financial Markets",
        "compliance_domain": "Investment Services and Trading Venues",
        "document_type": "Directive",
        "language": "EN",
        "formats": ["pdf", "html", "xml"],
    },
    {
        "document_id": "32024R1689",
        "celex": "32024R1689",
        "short_title": "AI_Act",
        "regulation_title": "Artificial Intelligence Act",
        "description": "Regulation laying down harmonised rules on artificial intelligence.",
        "issuing_authority": "European Parliament and Council of the European Union",
        "regulation_category": "Artificial Intelligence",
        "compliance_domain": "AI Governance and Risk Management",
        "document_type": "Regulation",
        "language": "EN",
        "formats": ["pdf", "html", "xml"],
    },
]


def create_session() -> requests.Session:
    """
    Create a requests session with retry logic.

    This helps with temporary network failures, rate limits,
    and unstable source responses.
    """

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": "AI-Regulatory-Compliance-Assistant/1.0",
        }
    )

    return session


def build_eurlex_url(
    celex_id: str,
    language: str,
    file_format: str,
) -> str:
    """
    Build EUR-Lex URL for a specific CELEX document and format.

    Examples:
        PDF:
        https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32016R0679&from=EN

        HTML:
        https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679&from=EN

        XML:
        https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:32016R0679&from=EN
    """

    format_map = {
        "pdf": "PDF",
        "html": "HTML",
        "xml": "XML",
    }

    if file_format not in format_map:
        raise ValueError(f"Unsupported EUR-Lex format: {file_format}")

    eurlex_format = format_map[file_format]

    return (
        f"https://eur-lex.europa.eu/legal-content/{language}/TXT/{eurlex_format}/"
        f"?uri=CELEX:{celex_id}&from={language}"
    )


def get_file_extension(file_format: str) -> str:
    """
    Return file extension for each supported format.
    """

    extension_map = {
        "pdf": ".pdf",
        "html": ".html",
        "xml": ".xml",
        "json": ".json",
    }

    if file_format not in extension_map:
        raise ValueError(f"No extension configured for format: {file_format}")

    return extension_map[file_format]


def get_accept_header(file_format: str) -> str:
    """
    Return the correct HTTP Accept header based on format.
    """

    accept_map = {
        "pdf": "application/pdf",
        "html": "text/html",
        "xml": "application/xml,text/xml",
        "json": "application/json",
    }

    return accept_map.get(file_format, "*/*")


def validate_downloaded_content(
    content: bytes,
    file_format: str,
) -> bool:
    """
    Basic validation to make sure the downloaded file matches the expected format.
    """

    stripped = content.lstrip()

    if file_format == "pdf":
        return stripped.startswith(b"%PDF")

    if file_format == "html":
        return b"<html" in stripped[:1000].lower() or b"<!doctype html" in stripped[:1000].lower()

    if file_format == "xml":
        return stripped.startswith(b"<?xml") or b"<" in stripped[:200]

    if file_format == "json":
        return stripped.startswith(b"{") or stripped.startswith(b"[")

    return True


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate SHA256 hash for lineage, deduplication, and traceability.
    """

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def download_single_format(
    session: requests.Session,
    document: dict[str, Any],
    file_format: str,
    base_out_dir: Path = RAW_DATA_DIR,
) -> dict[str, Any]:
    """
    Download one document in one format and return metadata.
    """

    if file_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{file_format}'. "
            f"Supported formats: {sorted(SUPPORTED_FORMATS)}"
        )

    celex_id = document["celex"]
    language = document.get("language", "EN")
    short_title = document["short_title"]

    source_url = build_eurlex_url(
        celex_id=celex_id,
        language=language,
        file_format=file_format,
    )

    format_dir = base_out_dir / file_format
    format_dir.mkdir(parents=True, exist_ok=True)

    extension = get_file_extension(file_format)

    file_name = f"{celex_id}_{short_title}_{language}{extension}"
    file_path = format_dir / file_name

    print(f"Downloading {short_title} as {file_format.upper()}")
    print(f"URL: {source_url}")

    headers = {
        "Accept": get_accept_header(file_format),
    }

    response = session.get(
        source_url,
        headers=headers,
        timeout=60,
    )

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")

    if not validate_downloaded_content(response.content, file_format):
        error_file = format_dir / f"{celex_id}_{short_title}_{language}_ERROR.html"
        error_file.write_bytes(response.content)

        raise ValueError(
            f"Downloaded content for {short_title} does not look like {file_format}. "
            f"Content-Type: {content_type}. "
            f"Debug response saved to: {error_file}"
        )

    file_path.write_bytes(response.content)

    file_size_bytes = file_path.stat().st_size
    file_sha256 = calculate_sha256(file_path)

    metadata = {
        "document_id": document["document_id"],
        "celex": celex_id,
        "short_title": short_title,
        "regulation_title": document["regulation_title"],
        "description": document["description"],
        "issuing_authority": document["issuing_authority"],
        "regulation_category": document["regulation_category"],
        "compliance_domain": document["compliance_domain"],
        "document_type": document["document_type"],
        "language": language,
        "source_system": "EUR-Lex",
        "source_url": source_url,
        "file_format": file_format,
        "local_path": str(file_path),
        "file_name": file_name,
        "file_size_bytes": file_size_bytes,
        "sha256": file_sha256,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
        "ingestion_status": "downloaded",
    }

    return metadata


def download_document(
    session: requests.Session,
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Download one regulatory document in all requested formats.
    """

    records = []

    for file_format in document["formats"]:
        try:
            metadata = download_single_format(
                session=session,
                document=document,
                file_format=file_format,
            )

            records.append(metadata)

            print(f"Downloaded: {metadata['local_path']}")
            print(f"SHA256: {metadata['sha256']}")
            print("-" * 80)

        except Exception as error:
            failed_record = {
                "document_id": document["document_id"],
                "celex": document["celex"],
                "short_title": document["short_title"],
                "regulation_title": document["regulation_title"],
                "source_system": "EUR-Lex",
                "source_url": build_eurlex_url(
                    celex_id=document["celex"],
                    language=document.get("language", "EN"),
                    file_format=file_format,
                ),
                "file_format": file_format,
                "ingestion_status": "failed",
                "error": str(error),
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            }

            records.append(failed_record)

            print(f"Failed to download {document['short_title']} as {file_format}: {error}")
            print("-" * 80)

    return records


def save_manifest(
    records: list[dict[str, Any]],
    manifest_path: Path = MANIFEST_PATH,
) -> None:
    """
    Save document metadata manifest as JSON.
    """

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=4, ensure_ascii=False)


def main() -> None:
    session = create_session()
    manifest_records: list[dict[str, Any]] = []

    for document in EU_REGULATORY_DOCUMENTS:
        document_records = download_document(
            session=session,
            document=document,
        )

        manifest_records.extend(document_records)

    save_manifest(manifest_records)

    successful_downloads = [
        record
        for record in manifest_records
        if record["ingestion_status"] == "downloaded"
    ]

    failed_downloads = [
        record
        for record in manifest_records
        if record["ingestion_status"] == "failed"
    ]

    print("Download summary")
    print("=" * 80)
    print(f"Successful downloads: {len(successful_downloads)}")
    print(f"Failed downloads: {len(failed_downloads)}")
    print(f"Manifest saved to: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()