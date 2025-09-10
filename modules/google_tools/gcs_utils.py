"""Google Cloud Storage helper utilities for expense documents."""
from google.cloud import storage
from dotenv import load_dotenv
import os
import re
import unicodedata
import datetime

load_dotenv()

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

_client = None


def _sanitize(component: str) -> str:
    """Return a filesystem-safe component name."""
    name = unicodedata.normalize("NFKD", component).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^\w\-_.]+", "_", name)


def _build_blob_path(building_id: int, building_name: str, expense_date, file_name: str) -> str:
    """Return the blob path for a document."""
    year = expense_date.strftime("%Y")
    month = expense_date.strftime("%m")
    safe_building = _sanitize(building_name)
    return f"Receipts/{building_id}-{safe_building}/{year}/{month}/{file_name}"

def get_client():
    """Return a cached Storage client."""
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def upload_document(
    file_path: str,
    file_name: str,
    building_id: int,
    building_name: str,
    expense_date,
):
    """Upload a document to GCS and return its object path."""
    client = get_client()
    bucket = client.bucket(BUCKET_NAME)

    blob_path = _build_blob_path(building_id, building_name, expense_date, file_name)

    blob = bucket.blob(blob_path)
    blob.upload_from_filename(file_path)
    # return a stable path that can be used to generate signed URLs later
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"


def _extract_blob_path(url: str) -> str:
    """Return the blob path from a GCS URL."""
    prefix = f"https://storage.googleapis.com/{BUCKET_NAME}/"
    path = url
    if url.startswith(prefix):
        path = url[len(prefix):]
    else:
        if f"/{BUCKET_NAME}/" in url:
            path = url.split(f"/{BUCKET_NAME}/", 1)[1]
    return path.split("?", 1)[0]


def delete_document(
    building_id: int,
    building_name: str,
    expense_date,
    file_name: str,
) -> None:
    """Delete a document from GCS."""
    client = get_client()
    bucket = client.bucket(BUCKET_NAME)

    blob_path = _build_blob_path(building_id, building_name, expense_date, file_name)

    blob = bucket.blob(blob_path)
    blob.delete()


def delete_document_by_url(file_url: str) -> None:
    """Delete a document from GCS using its stored URL."""
    client = get_client()
    bucket = client.bucket(BUCKET_NAME)
    blob_path = _extract_blob_path(file_url)
    blob = bucket.blob(blob_path)
    blob.delete()


def get_document_url(
    building_id: int,
    building_name: str,
    expense_date,
    file_name: str,
    expires_in: int = 3600,
) -> str:
    """Return a signed URL for downloading a document."""
    client = get_client()
    bucket = client.bucket(BUCKET_NAME)
    blob_path = _build_blob_path(building_id, building_name, expense_date, file_name)
    blob = bucket.blob(blob_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expires_in),
        method="GET",
    )


def get_document_url_from_file(file_url: str, expires_in: int = 3600) -> str:
    """Return a signed download URL for a stored document."""
    client = get_client()
    bucket = client.bucket(BUCKET_NAME)
    blob_path = _extract_blob_path(file_url)
    blob = bucket.blob(blob_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expires_in),
        method="GET",
    )

