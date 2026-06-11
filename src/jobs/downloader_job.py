"""
src/jobs/downloader_job.py

Regulatory data downloader — runs as a Databricks job.

Downloads all documents automatically:
- EUR-Lex PDFs via CELLAR REST API (two-step: RDF metadata → PDF/A binary)
- EBA HTML page
- ECB XML feed

Change detection:
- EUR-Lex: compares CELLAR lastModificationDate against previous manifest.
- EBA/ECB: sends If-Modified-Since header; skips on 304 Not Modified.
  Falls back to always downloading if server does not support it.

If no document changed, sets changes_detected=false via task values so
downstream tasks (Bronze → Gold) can be skipped via a condition task.

Write strategy (Unity Catalog Volume POSIX limitations in serverless):
- PDFs (binary):    SDK files.upload() to Volume
- HTML/XML (text):  dbutils.fs.put() to Volume
- Manifest (JSON):  dbutils.fs.put() to Volume

Writes to:
- /Volumes/accenture2026dbcks/team4/volume/raw/pdf/
- /Volumes/accenture2026dbcks/team4/volume/raw/html/
- /Volumes/accenture2026dbcks/team4/volume/raw/xml/
- /Volumes/accenture2026dbcks/team4/volume/metadata/document_manifest.json
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from databricks.sdk import WorkspaceClient


# =============================================================================
# Make src/ importable (same pattern as bronze_ingestion.py)
# =============================================================================

def _add_src_to_path() -> None:
    candidate_dirs = []

    try:
        current_file = Path(__file__).resolve()
        candidate_dirs.append(current_file.parents[1])
    except NameError:
        pass

    cwd = Path.cwd()
    candidate_dirs.extend([
        cwd,
        cwd / "src",
        cwd / "files" / "src",
        cwd.parent,
        cwd.parent / "src",
        cwd.parent / "files" / "src",
    ])

    for candidate in candidate_dirs:
        if (candidate / "regulatory_corpus.py").exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            print(f"Added to Python path: {candidate}")
            return

    raise FileNotFoundError("Could not find regulatory_corpus.py")


_add_src_to_path()

from regulatory_corpus import EUR_LEX_DOCUMENTS, WEB_DOCUMENTS  # noqa: E402


# =============================================================================
# Volume paths
# =============================================================================

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


# =============================================================================
# Corpus normalisation
# =============================================================================

def _expand_eurlex(entry: dict[str, Any]) -> dict[str, Any]:
    celex = entry["celex"]
    short_title = entry['short_title']
    return {
        "document_id": celex,
        "celex": celex,
        "short_title": entry["short_title"],
        "title": None,
        "category": entry["category"],
        "source_system": "EUR-Lex",
        "source_url": (
            f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:{celex}"
        ),
        "file_format": "pdf",
        "file_name": f"{celex}_EN_{short_title}.pdf",
    }


def _expand_web(entry: dict[str, Any]) -> dict[str, Any]:
    return {"celex": None, **entry}


DOCUMENTS: list[dict[str, Any]] = [
    *[_expand_eurlex(e) for e in EUR_LEX_DOCUMENTS],
    *[_expand_web(e) for e in WEB_DOCUMENTS],
]


# =============================================================================
# Helpers
# =============================================================================

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


# =============================================================================
# Manifest
# =============================================================================

def load_previous_manifest() -> dict[str, dict[str, Any]]:
    """
    Load the manifest from the previous run, keyed by document_id.
    Uses Spark to avoid POSIX read limitations on this volume.
    Returns empty dict if no manifest exists yet.
    """
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        df = (
            spark.read
            .option("multiLine", "true")
            .json(str(MANIFEST_PATH))
        )
        return {
            row["document_id"]: row.asDict(recursive=True)
            for row in df.collect()
        }
    except Exception:
        return {}


def save_manifest(records: list[dict[str, Any]]) -> None:
    content = json.dumps(records, indent=4, ensure_ascii=False)
    dbutils.fs.put(str(MANIFEST_PATH), content, overwrite=True)  # noqa: F821
    print(f"Manifest saved to: {MANIFEST_PATH}")


# =============================================================================
# Metadata builders
# =============================================================================

def create_metadata(
    document: dict[str, Any],
    file_path: Path,
    cellar_last_modified: str | None = None,
    title: str | None = None,
    last_modified_header: str | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "celex": document.get("celex"),
        "short_title": document["short_title"],
        "title": title or document.get("title"),
        "category": document["category"],
        "language": "EN",
        "source_system": document["source_system"],
        "source_url": document["source_url"],
        "file_format": document["file_format"],
        "file_name": file_path.name,
        "volume_path": str(file_path),
        "file_size_bytes": None,
        "sha256": None,
        "cellar_last_modified": cellar_last_modified,
        "last_modified_header": last_modified_header,
        "downloaded_at_utc": now_utc(),
        "ingestion_status": "downloaded",
        "acquisition_method": "automatic_download",
    }


def create_failed_metadata(document: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "celex": document.get("celex"),
        "short_title": document["short_title"],
        "title": document.get("title"),
        "category": document["category"],
        "source_system": document["source_system"],
        "source_url": document["source_url"],
        "file_format": document["file_format"],
        "ingestion_status": "failed",
        "error": str(error),
        "downloaded_at_utc": now_utc(),
    }


# =============================================================================
# CELLAR helpers
# =============================================================================

def _extract_english_cellar_id(rdf_text: str) -> str:
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


def _extract_modification_date(rdf_text: str) -> str | None:
    match = re.search(r'lastModificationDate[^>]*>([^<]+)</j', rdf_text)
    return match.group(1).strip() if match else None


def _extract_title(rdf_text: str) -> str | None:
    match = re.search(r'<j\.0:title>([^<]+)</j\.0:title>', rdf_text)
    return match.group(1).strip() if match else None


# =============================================================================
# EUR-Lex PDF acquisition
# =============================================================================

def acquire_eurlex_document(
    document: dict[str, Any],
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """
    Download a EUR-Lex PDF via CELLAR, skipping if unchanged.

    Returns (metadata, changed) where changed=False means the document
    was unchanged and the download was skipped.
    """
    celex_id = document["celex"]
    file_path = output_dir_for("pdf") / document["file_name"]

    # Step 1: fetch RDF metadata
    rdf_response = requests.get(
        f"https://publications.europa.eu/resource/celex/{celex_id}",
        headers={
            "Accept": "application/rdf+xml",
            "Accept-Language": "eng",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    rdf_response.raise_for_status()

    cellar_id = _extract_english_cellar_id(rdf_response.text)
    mod_date = _extract_modification_date(rdf_response.text)
    title = _extract_title(rdf_response.text)

    # Step 2: change detection
    if (
        previous is not None
        and previous.get("ingestion_status") == "downloaded"
        and previous.get("cellar_last_modified") == mod_date
        and mod_date is not None
    ):
        print(f"[{celex_id}] Unchanged (last modified: {mod_date}). Skipping.")
        return {**previous, "downloaded_at_utc": now_utc()}, False

    # Step 3: download and upload
    print(f"[{celex_id}] CELLAR expression: {cellar_id}")
    time.sleep(1)

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
        raise ValueError(f"Expected PDF but got {content_type}. URL: {pdf_url}")

    pdf_bytes = pdf_response.content
    print(f"[{celex_id}] Downloaded {len(pdf_bytes):,} bytes")

    WorkspaceClient().files.upload(
        file_path=str(file_path),
        contents=io.BytesIO(pdf_bytes),
        overwrite=True,
    )
    print(f"[{celex_id}] Uploaded to Volume")

    return create_metadata(
        document,
        file_path,
        cellar_last_modified=mod_date,
        title=title,
    ), True


# =============================================================================
# Web document acquisition (EBA, ECB)
# =============================================================================

def acquire_web_document(
    document: dict[str, Any],
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """
    Download an EBA/ECB document with HTTP conditional request change detection.

    Sends If-Modified-Since if a previous Last-Modified is stored.
    Returns (metadata, changed=False) on 304 Not Modified.
    Falls back to always downloading if the server does not support
    conditional requests.

    Returns (metadata, changed) tuple.
    """
    target_path = output_dir_for(document["file_format"]) / document["file_name"]

    headers: dict[str, str] = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

    if previous and previous.get("last_modified_header"):
        headers["If-Modified-Since"] = previous["last_modified_header"]

    response = requests.get(
        document["source_url"],
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )

    if response.status_code == 304:
        print(f"[{document['short_title']}] Unchanged (304 Not Modified). Skipping.")
        return {**previous, "downloaded_at_utc": now_utc()}, False

    response.raise_for_status()

    last_modified = response.headers.get("Last-Modified")
    dbutils.fs.put(str(target_path), response.text, overwrite=True)  # noqa: F821

    return create_metadata(
        document,
        target_path,
        last_modified_header=last_modified,
    ), True


# =============================================================================
# Main
# =============================================================================

def download_corpus() -> list[dict[str, Any]]:
    previous_manifest = load_previous_manifest()
    print(f"Loaded previous manifest: {len(previous_manifest)} records")
    print("-" * 80)

    manifest: list[dict[str, Any]] = []
    changes_detected = False

    for i, document in enumerate(DOCUMENTS):
        print(f"Processing: {document['short_title']}")
        try:
            previous = previous_manifest.get(document["document_id"])

            if document["file_format"] == "pdf":
                metadata, changed = acquire_eurlex_document(document, previous)
            else:
                metadata, changed = acquire_web_document(document, previous)

            if changed:
                changes_detected = True

            print(f"Ready: {document['file_name']}")

        except Exception as error:
            print(f"Failed: {document['short_title']}")
            print(f"Reason: {error}")
            metadata = create_failed_metadata(document, error)
            changes_detected = True  # failures should always trigger the pipeline

        manifest.append(metadata)
        print("-" * 80)

        if i < len(DOCUMENTS) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    save_manifest(manifest)

    print(f"Changes detected: {changes_detected}")
    dbutils.jobs.taskValues.set(  # noqa: F821
        key="changes_detected",
        value=str(changes_detected).lower(),
    )

    return manifest


if __name__ == "__main__":
    download_corpus()