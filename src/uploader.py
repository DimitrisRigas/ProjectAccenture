"""
src/upload_to_volume.py

Upload downloaded EU regulatory documents to a Databricks Unity Catalog Volume.

Uploads:
- PDFs from data/raw/pdf/
- if no raw PDFs exist, PDFs from data/manual/pdf/
- HTML files from data/raw/html/
- XML files from data/raw/xml/
- document manifest from data/metadata/document_manifest.json

This supports:
- Project step 6.5 Databricks & Data Engineering Implementation
- Project step 6.6 AI-Ready Document Processing
"""

from __future__ import annotations

from pathlib import Path

from databricks.sdk import WorkspaceClient


# Because this file is located at:
# ProjectAccenture/src/upload_to_volume.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
RAW_PDF_DIR = RAW_DIR / "pdf"
RAW_HTML_DIR = RAW_DIR / "html"
RAW_XML_DIR = RAW_DIR / "xml"

MANUAL_PDF_DIR = DATA_DIR / "manual" / "pdf"

METADATA_DIR = DATA_DIR / "metadata"
MANIFEST_PATH = METADATA_DIR / "document_manifest.json"


# Change these 3 values to match your Databricks setup.
CATALOG = "accenture2026dbcks"
SCHEMA = "team4"
VOLUME = "data"


DATABRICKS_VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

DATABRICKS_RAW_PATH = f"{DATABRICKS_VOLUME_PATH}/raw"
DATABRICKS_RAW_PDF_PATH = f"{DATABRICKS_RAW_PATH}/pdf"
DATABRICKS_RAW_HTML_PATH = f"{DATABRICKS_RAW_PATH}/html"
DATABRICKS_RAW_XML_PATH = f"{DATABRICKS_RAW_PATH}/xml"
DATABRICKS_METADATA_PATH = f"{DATABRICKS_VOLUME_PATH}/metadata"


def get_client() -> WorkspaceClient:
    """
    Create Databricks workspace client.

    The Databricks SDK reads authentication from:
    - environment variables, for example DATABRICKS_HOST and DATABRICKS_TOKEN
    - Databricks CLI configuration
    - notebook environment, if running inside Databricks
    """

    return WorkspaceClient()


def create_volume_folders(client: WorkspaceClient) -> None:
    """
    Create folders in the Unity Catalog Volume.
    """

    folders = [
        DATABRICKS_VOLUME_PATH,
        DATABRICKS_RAW_PATH,
        DATABRICKS_RAW_PDF_PATH,
        DATABRICKS_RAW_HTML_PATH,
        DATABRICKS_RAW_XML_PATH,
        DATABRICKS_METADATA_PATH,
    ]

    for folder in folders:
        try:
            client.files.create_directory(folder)
            print(f"Created folder: {folder}")
        except Exception:
            print(f"Folder already exists or could not be created: {folder}")


def upload_file(
    client: WorkspaceClient,
    local_path: Path,
    target_folder: str,
) -> None:
    """
    Upload one file to a Databricks Unity Catalog Volume.
    """

    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    target_path = f"{target_folder}/{local_path.name}"
    file_size_mb = local_path.stat().st_size / (1024 * 1024)

    print(f"Uploading: {local_path}")
    print(f"Size: {file_size_mb:.2f} MB")
    print(f"Target: {target_path}")

    with local_path.open("rb") as file:
        client.files.upload(
            file_path=target_path,
            contents=file,
            overwrite=True,
        )

    print("Upload completed")
    print("-" * 80)


def upload_folder(
    client: WorkspaceClient,
    local_folder: Path,
    target_folder: str,
    pattern: str,
) -> int:
    """
    Upload all files matching a pattern from a local folder.
    """

    if not local_folder.exists():
        print(f"Skipping missing folder: {local_folder}")
        return 0

    files = sorted(local_folder.glob(pattern))

    if not files:
        print(f"No files found in: {local_folder}")
        return 0

    uploaded_count = 0

    for file_path in files:
        upload_file(
            client=client,
            local_path=file_path,
            target_folder=target_folder,
        )
        uploaded_count += 1

    return uploaded_count


def choose_pdf_folder() -> Path:
    """
    Prefer data/raw/pdf/.

    If raw PDFs do not exist, fallback to data/manual/pdf/.
    This is useful when EUR-Lex PDFs were manually downloaded.
    """

    raw_pdfs = list(RAW_PDF_DIR.glob("*.pdf")) if RAW_PDF_DIR.exists() else []

    if raw_pdfs:
        print(f"Using raw PDF folder: {RAW_PDF_DIR}")
        return RAW_PDF_DIR

    manual_pdfs = list(MANUAL_PDF_DIR.glob("*.pdf")) if MANUAL_PDF_DIR.exists() else []

    if manual_pdfs:
        print(f"No raw PDFs found in: {RAW_PDF_DIR}")
        print(f"Using manual PDF folder instead: {MANUAL_PDF_DIR}")
        return MANUAL_PDF_DIR

    print(f"No PDFs found in: {RAW_PDF_DIR}")
    print(f"No PDFs found in: {MANUAL_PDF_DIR}")

    return RAW_PDF_DIR


def upload_manifest(client: WorkspaceClient) -> int:
    """
    Upload document_manifest.json if it exists.
    """

    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        print("Run downloader.py first.")
        return 0

    upload_file(
        client=client,
        local_path=MANIFEST_PATH,
        target_folder=DATABRICKS_METADATA_PATH,
    )

    return 1


def main() -> None:
    """
    Main upload workflow.
    """

    if not RAW_DIR.exists() and not MANUAL_PDF_DIR.exists():
        raise FileNotFoundError(
            "No local data found.\n"
            f"Expected raw folder: {RAW_DIR}\n"
            f"Expected manual PDF folder: {MANUAL_PDF_DIR}\n"
            "Run downloader.py first or place PDFs in data/manual/pdf/."
        )

    print("=" * 80)
    print("Uploading regulatory files to Databricks Unity Catalog Volume")
    print("=" * 80)
    print(f"Target volume: {DATABRICKS_VOLUME_PATH}")
    print("=" * 80)

    client = get_client()
    create_volume_folders(client)

    total_uploaded = 0

    pdf_folder = choose_pdf_folder()

    total_uploaded += upload_folder(
        client=client,
        local_folder=pdf_folder,
        target_folder=DATABRICKS_RAW_PDF_PATH,
        pattern="*.pdf",
    )

    total_uploaded += upload_folder(
        client=client,
        local_folder=RAW_HTML_DIR,
        target_folder=DATABRICKS_RAW_HTML_PATH,
        pattern="*.html",
    )

    total_uploaded += upload_folder(
        client=client,
        local_folder=RAW_XML_DIR,
        target_folder=DATABRICKS_RAW_XML_PATH,
        pattern="*.xml",
    )

    total_uploaded += upload_manifest(client)

    print("=" * 80)
    print("Upload completed")
    print(f"Total uploaded files: {total_uploaded}")
    print(f"Databricks volume path: {DATABRICKS_VOLUME_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()