"""Google Drive API client service."""
import json
import logging
from dataclasses import dataclass
from typing import Any
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io

logger = logging.getLogger(__name__)


@dataclass
class DriveFileInfo:
    """Drive file information."""
    id: str
    name: str
    mime_type: str
    md5_checksum: str | None


class DriveService:
    """Google Drive API service using service account authentication."""

    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    # Supported MIME types for documents
    PDF_MIME_TYPE = 'application/pdf'
    GOOGLE_DOC_MIME_TYPE = 'application/vnd.google-apps.document'
    GOOGLE_FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'

    # Allowed export MIME types for Google Docs
    ALLOWED_EXPORT_TYPES = {
        'application/pdf',
        'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/html'
    }

    def __init__(self, credentials_json: str | None):
        """Initialize Drive service with service account credentials.

        Args:
            credentials_json: JSON string or file path to service account credentials.
                            If None, service will be None (not configured).
        """
        self.service = None

        if credentials_json is None:
            logger.warning("Google Drive service not configured (no credentials provided)")
            return

        try:
            # Determine if it's a file path or JSON string
            credentials_info = self._load_credentials(credentials_json)

            # Create credentials from service account info
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=self.SCOPES
            )

            # Build the Drive API service
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise

    def _load_credentials(self, credentials_json: str) -> dict[str, Any]:
        """Load credentials from JSON string or file path.

        Args:
            credentials_json: JSON string or file path.

        Returns:
            Dictionary containing service account credentials.
        """
        # Try to parse as JSON string first
        try:
            return json.loads(credentials_json)
        except json.JSONDecodeError:
            # If that fails, treat as file path
            path = Path(credentials_json)
            if path.exists():
                with open(path, 'r') as f:
                    return json.load(f)
            else:
                raise ValueError(f"Invalid credentials: not valid JSON and file not found at {path}")

    def list_files(self, folder_id: str) -> list[DriveFileInfo]:
        """List PDF and Google Doc files in a folder.

        Args:
            folder_id: Google Drive folder ID.

        Returns:
            List of DriveFileInfo objects.
        """
        if self.service is None:
            logger.warning("Drive service not configured")
            return []

        try:
            # Query for PDF files and Google Docs in the specified folder
            query = (
                f"'{folder_id}' in parents and "
                f"(mimeType='{self.PDF_MIME_TYPE}' or mimeType='{self.GOOGLE_DOC_MIME_TYPE}') and "
                f"trashed=false"
            )

            # Handle pagination to get all files
            all_files = []
            page_token = None

            while True:
                results = self.service.files().list(
                    q=query,
                    fields='nextPageToken, files(id, name, mimeType, md5Checksum)',
                    pageSize=1000,
                    pageToken=page_token
                ).execute()

                files = results.get('files', [])
                all_files.extend(files)

                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            return [
                DriveFileInfo(
                    id=file['id'],
                    name=file['name'],
                    mime_type=file['mimeType'],
                    md5_checksum=file.get('md5Checksum')  # Google Docs don't have MD5
                )
                for file in all_files
            ]

        except HttpError as e:
            logger.error(f"Error listing files from folder {folder_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            raise

    def download_file(self, file_id: str) -> bytes | None:
        """Download file content (for PDFs).

        Args:
            file_id: Google Drive file ID.

        Returns:
            File content as bytes, or None if service not configured.
        """
        if self.service is None:
            logger.warning("Drive service not configured")
            return None

        try:
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            return file_buffer.getvalue()

        except HttpError as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            raise

    def export_google_doc(self, file_id: str, mime_type: str = 'application/pdf') -> bytes | None:
        """Export Google Doc to specified format.

        Args:
            file_id: Google Drive file ID.
            mime_type: Export MIME type (default: application/pdf).

        Returns:
            Exported file content as bytes, or None if service not configured.

        Raises:
            ValueError: If mime_type is not in ALLOWED_EXPORT_TYPES.
        """
        if self.service is None:
            logger.warning("Drive service not configured")
            return None

        # Validate MIME type
        if mime_type not in self.ALLOWED_EXPORT_TYPES:
            raise ValueError(
                f"Invalid export MIME type: {mime_type}. "
                f"Allowed types: {', '.join(sorted(self.ALLOWED_EXPORT_TYPES))}"
            )

        try:
            request = self.service.files().export(
                fileId=file_id,
                mimeType=mime_type
            )

            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Export progress: {int(status.progress() * 100)}%")

            return file_buffer.getvalue()

        except HttpError as e:
            logger.error(f"Error exporting Google Doc {file_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error exporting Google Doc: {e}")
            raise

    def verify_folder_access(self, folder_id: str) -> tuple[bool, str | None]:
        """Verify access to a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID.

        Returns:
            Tuple of (success: bool, error_message: str | None).
        """
        if self.service is None:
            return False, "Drive service not configured"

        try:
            # Try to get folder metadata
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id,name,mimeType'
            ).execute()

            # Verify it's actually a folder
            if folder.get('mimeType') != self.GOOGLE_FOLDER_MIME_TYPE:
                return False, f"ID {folder_id} is not a folder (type: {folder.get('mimeType')})"

            logger.info(f"Successfully verified access to folder: {folder.get('name')}")
            return True, None

        except HttpError as e:
            error_msg = f"HTTP error accessing folder {folder_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error accessing folder {folder_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
