"""
gcs_manager.py - High-Performance GCS Signed URL Stream Architecture

Manages direct, non-proxied data streaming between Ephemeral Sandboxes and GCS
via pre-signed V4 URLs, keeping orchestrator memory at baseline thresholds.
"""

import datetime
import os
from typing import Any

import structlog
from google.cloud import storage

from .config import Settings

logger = structlog.get_logger()


class GCSManager:
    """Manages direct, non-proxied data streaming between Ephemeral Sandboxes and GCS.

    Ensures that orchestrator memory never exceeds baseline thresholds by
    issuing short-lived pre-signed V4 URLs that sandboxes use to GET/PUT
    objects directly against the bucket.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the GCS client and resolve the target bucket.

        Falls back cleanly onto Application Default Credentials (ADC) or
        Modal-injected Service Account secrets.

        Args:
            settings: System settings containing GCP project + bucket config.
        """
        self.settings = settings
        # Falls back cleanly onto ADC / Modal injected Service Account secrets
        self.storage_client = storage.Client(project=self.settings.gcp_project_id)
        self.bucket = self.storage_client.bucket(self.settings.gcs_bucket_name)

    def generate_download_signed_url(self, blob_name: str) -> str:
        """Generate a short-lived pre-signed V4 GET URL for ``blob_name``.

        Sandboxes use this URL to download input artifacts directly from GCS
        without routing bytes through the orchestrator.

        Args:
            blob_name: Object key within the configured bucket.

        Returns:
            A time-limited HTTPS URL granting read access to the object.
        """
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=self.settings.gcs_signed_url_ttl),
            method="GET",
        )
        return url

    def generate_upload_signed_url(
        self, blob_name: str, content_type: str = "application/octet-stream"
    ) -> str:
        """Generate a short-lived pre-signed V4 PUT URL for ``blob_name``.

        Sandboxes use this URL to stream output artifacts directly into GCS
        without routing bytes through the orchestrator.

        Args:
            blob_name: Object key within the configured bucket.
            content_type: MIME type to enforce on upload (must match the
                ``Content-Type`` header sent by the PUT request).

        Returns:
            A time-limited HTTPS URL granting write access to the object.
        """
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=self.settings.gcs_signed_url_ttl),
            method="PUT",
            content_type=content_type,
        )
        return url

    def get_blob_metadata(self, blob_name: str) -> dict[str, Any] | None:
        """Extract statistical metadata for analytical record keeping.

        Args:
            blob_name: Object key within the configured bucket.

        Returns:
            A dict with ``file_name``, ``gcs_uri``, ``size_bytes``, and
            ``content_type`` — or ``None`` if the blob does not exist.
        """
        blob = self.bucket.get_blob(blob_name)
        if not blob:
            return None
        return {
            "file_name": os.path.basename(blob_name),
            "gcs_uri": f"gs://{self.settings.gcs_bucket_name}/{blob_name}",
            "size_bytes": blob.size,
            "content_type": blob.content_type or "application/octet-stream",
        }
