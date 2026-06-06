"""
Upload downloaded EU regulatory documents to a Databricks Unity Catalog Volume.

This script uploads:
- raw PDF files
- raw HTML files
- raw XML files
- metadata manifest JSON

Project step:
    6.5 Databricks & Data Engineering Implementation
    6.6 AI-Ready Document Processing

file: ex2_upload_to_volume.py
"""

from __future__ import annotations

from pathlib import Path

from databricks.sdk import WorkspaceClient


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"
VOLUME = "volume"

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
LOCAL_RAW_DIR = Path("data") / "raw"
LOCAL_METADATA_DIR = Path("data") / "metadata"


def get_workspace_client() -> WorkspaceClient:
    """
    Create Databricks workspace client.

    Authentication is handled by Databricks SDK.
    Usually it reads from:
    - DATABRICKS_HOST
    - DATABRICKS_TOKEN

    or from an existing Databricks CLI profile.
    """

    return WorkspaceClient()


def upload_file_to_volume(
    client: WorkspaceClient,
    local_file: Path,
    target_file_path: str,
) -> None:
    """
    Upload one local file to a Databricks Unity Catalog Volume.
    """

    with local_file.open("rb") as file:
        client.files.upload(
            file_path=target_file_path,
            contents=file,
            overwrite=True,
        )

    print(f"Uploaded: {local_file} -> {target_file_path}")


def upload_directory_files(
    client: WorkspaceClient,
    local_directory: Path,
    volume_subdirectory: str,
    pattern: str,
) -> int:
    """
    Upload files from one local directory to one Volume subdirectory.
    """

    if not local_directory.exists():
        print(f"Skipping missing folder: {local_directory}")
        return 0

    files = sorted(local_directory.glob(pattern))

    if not files:
        print(f"No files found in: {local_directory}")
        return 0

    uploaded_count = 0

    for local_file in files:
        target_file_path = (
            f"{VOLUME_PATH}/{volume_subdirectory}/{local_file.name}"
        )

        upload_file_to_volume(
            client=client,
            local_file=local_file,
            target_file_path=target_file_path,
        )

        uploaded_count += 1

    return uploaded_count


def upload_manifest(client: WorkspaceClient) -> int:
    """
    Upload metadata manifest JSON to the Volume.
    """

    manifest_path = LOCAL_METADATA_DIR / "document_manifest.json"

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        print("Run ex1_download_documents.py first.")
        return 0

    target_file_path = f"{VOLUME_PATH}/metadata/{manifest_path.name}"

    upload_file_to_volume(
        client=client,
        local_file=manifest_path,
        target_file_path=target_file_path,
    )

    return 1


def main() -> None:
    if not LOCAL_RAW_DIR.exists():
        raise FileNotFoundError(
            f"Folder not found: {LOCAL_RAW_DIR}. "
            "Run ex1_download_documents.py first."
        )

    client = get_workspace_client()

    print("Uploading files to Databricks Volume")
    print("=" * 80)
    print(f"Target Volume path: {VOLUME_PATH}")
    print("=" * 80)

    total_uploaded = 0

    total_uploaded += upload_directory_files(
        client=client,
        local_directory=LOCAL_RAW_DIR / "pdf",
        volume_subdirectory="raw/pdf",
        pattern="*.pdf",
    )

    total_uploaded += upload_directory_files(
        client=client,
        local_directory=LOCAL_RAW_DIR / "html",
        volume_subdirectory="raw/html",
        pattern="*.html",
    )

    total_uploaded += upload_directory_files(
        client=client,
        local_directory=LOCAL_RAW_DIR / "xml",
        volume_subdirectory="raw/xml",
        pattern="*.xml",
    )

    total_uploaded += upload_manifest(client)

    print("=" * 80)
    print(f"Upload completed. Total uploaded files: {total_uploaded}")
    print(f"Databricks Volume path: {VOLUME_PATH}")


if __name__ == "__main__":
    main()