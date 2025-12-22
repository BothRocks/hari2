"""Tests for Google Drive service."""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.drive.client import DriveService, DriveFileInfo


@pytest.fixture
def mock_service_account_info():
    """Mock service account credentials."""
    return {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7W\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    }


@pytest.fixture
def mock_drive_api():
    """Mock Google Drive API service."""
    mock_service = MagicMock()

    # Mock files().list() for listing files
    mock_files_list = MagicMock()
    mock_files_list.execute.return_value = {
        'files': [
            {
                'id': 'file1',
                'name': 'test.pdf',
                'mimeType': 'application/pdf',
                'md5Checksum': 'abc123'
            },
            {
                'id': 'file2',
                'name': 'document.gdoc',
                'mimeType': 'application/vnd.google-apps.document',
                'md5Checksum': None
            }
        ]
    }
    mock_service.files().list.return_value = mock_files_list

    # Mock files().get_media() for downloading
    mock_get_media = MagicMock()
    mock_get_media.execute.return_value = b'PDF content here'
    mock_service.files().get_media.return_value = mock_get_media

    # Mock files().export() for Google Docs
    mock_export = MagicMock()
    mock_export.execute.return_value = b'Exported PDF content'
    mock_service.files().export.return_value = mock_export

    # Mock files().get() for folder verification
    mock_get = MagicMock()
    mock_get.execute.return_value = {
        'id': 'folder123',
        'name': 'Test Folder',
        'mimeType': 'application/vnd.google-apps.folder'
    }
    mock_service.files().get.return_value = mock_get

    return mock_service


class TestDriveService:
    """Test DriveService class."""

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_init_with_json_string(self, mock_build, mock_credentials, mock_service_account_info, mock_drive_api):
        """Test initialization with JSON string credentials."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        service = DriveService(json_string)

        assert service.service is not None
        mock_credentials.from_service_account_info.assert_called_once()
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_credentials.from_service_account_info.return_value)

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    @patch('app.services.drive.client.Path')
    def test_init_with_file_path(self, mock_path, mock_build, mock_credentials, mock_service_account_info, mock_drive_api):
        """Test initialization with file path credentials."""
        # Mock Path.exists() to return True
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock open to return the credentials
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = MagicMock()
            mock_file.__enter__.return_value.read = MagicMock(return_value=json.dumps(mock_service_account_info))
            mock_open.return_value = mock_file
            mock_build.return_value = mock_drive_api

            service = DriveService('/path/to/credentials.json')

            assert service.service is not None
            mock_credentials.from_service_account_info.assert_called_once()

    def test_init_with_none_returns_none_service(self):
        """Test initialization with None returns service as None."""
        service = DriveService(None)
        assert service.service is None

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_list_files(self, mock_build, mock_credentials, mock_service_account_info, mock_drive_api):
        """Test listing files in a folder."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        service = DriveService(json_string)
        files = service.list_files('folder123')

        assert len(files) == 2
        assert files[0].id == 'file1'
        assert files[0].name == 'test.pdf'
        assert files[0].mime_type == 'application/pdf'
        assert files[0].md5_checksum == 'abc123'

        assert files[1].id == 'file2'
        assert files[1].name == 'document.gdoc'
        assert files[1].mime_type == 'application/vnd.google-apps.document'
        assert files[1].md5_checksum is None

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_list_files_no_service(self, mock_build, mock_credentials):
        """Test listing files when service is None."""
        service = DriveService(None)
        files = service.list_files('folder123')
        assert files == []

    @patch('app.services.drive.client.MediaIoBaseDownload')
    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_download_file(self, mock_build, mock_credentials, mock_media_download, mock_service_account_info, mock_drive_api):
        """Test downloading a file."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        # Mock MediaIoBaseDownload to simulate download completion
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)  # done=True on first call
        mock_media_download.return_value = mock_downloader

        # Mock the file buffer to return content
        with patch('app.services.drive.client.io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b'PDF content here'
            mock_bytesio.return_value = mock_buffer

            service = DriveService(json_string)
            content = service.download_file('file1')

            assert content == b'PDF content here'
            mock_drive_api.files().get_media.assert_called_once_with(fileId='file1')

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_download_file_no_service(self, mock_build, mock_credentials):
        """Test downloading file when service is None."""
        service = DriveService(None)
        content = service.download_file('file1')
        assert content is None

    @patch('app.services.drive.client.MediaIoBaseDownload')
    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_export_google_doc(self, mock_build, mock_credentials, mock_media_download, mock_service_account_info, mock_drive_api):
        """Test exporting a Google Doc."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        # Mock MediaIoBaseDownload to simulate export completion
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)  # done=True on first call
        mock_media_download.return_value = mock_downloader

        # Mock the file buffer to return content
        with patch('app.services.drive.client.io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b'Exported PDF content'
            mock_bytesio.return_value = mock_buffer

            service = DriveService(json_string)
            content = service.export_google_doc('doc123', 'application/pdf')

            assert content == b'Exported PDF content'
            mock_drive_api.files().export.assert_called_once_with(
                fileId='doc123',
                mimeType='application/pdf'
            )

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_export_google_doc_no_service(self, mock_build, mock_credentials):
        """Test exporting Google Doc when service is None."""
        service = DriveService(None)
        content = service.export_google_doc('doc123', 'application/pdf')
        assert content is None

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_verify_folder_access_success(self, mock_build, mock_credentials, mock_service_account_info, mock_drive_api):
        """Test verifying folder access successfully."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        service = DriveService(json_string)
        success, error = service.verify_folder_access('folder123')

        assert success is True
        assert error is None
        mock_drive_api.files().get.assert_called_once_with(
            fileId='folder123',
            fields='id,name,mimeType'
        )

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_verify_folder_access_failure(self, mock_build, mock_credentials, mock_service_account_info, mock_drive_api):
        """Test verifying folder access with error."""
        json_string = json.dumps(mock_service_account_info)
        mock_build.return_value = mock_drive_api

        # Simulate an error
        from googleapiclient.errors import HttpError
        mock_response = Mock()
        mock_response.status = 404
        mock_drive_api.files().get().execute.side_effect = HttpError(mock_response, b'Not found')

        service = DriveService(json_string)
        success, error = service.verify_folder_access('folder123')

        assert success is False
        assert error is not None
        assert 'Not found' in error or '404' in error

    @patch('app.services.drive.client.service_account.Credentials')
    @patch('app.services.drive.client.build')
    def test_verify_folder_access_no_service(self, mock_build, mock_credentials):
        """Test verifying folder access when service is None."""
        service = DriveService(None)
        success, error = service.verify_folder_access('folder123')

        assert success is False
        assert error == "Drive service not configured"


class TestDriveFileInfo:
    """Test DriveFileInfo dataclass."""

    def test_drive_file_info_creation(self):
        """Test creating DriveFileInfo instance."""
        file_info = DriveFileInfo(
            id='file123',
            name='test.pdf',
            mime_type='application/pdf',
            md5_checksum='abc123'
        )

        assert file_info.id == 'file123'
        assert file_info.name == 'test.pdf'
        assert file_info.mime_type == 'application/pdf'
        assert file_info.md5_checksum == 'abc123'

    def test_drive_file_info_with_none_checksum(self):
        """Test DriveFileInfo with None checksum (Google Docs)."""
        file_info = DriveFileInfo(
            id='doc123',
            name='document.gdoc',
            mime_type='application/vnd.google-apps.document',
            md5_checksum=None
        )

        assert file_info.md5_checksum is None
