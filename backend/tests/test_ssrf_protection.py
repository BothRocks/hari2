"""Tests for SSRF protection in URL validation."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.core.security import validate_url, WHITELISTED_DOMAINS
from app.services.pipeline.url_fetcher import fetch_url_content


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self):
        """Valid HTTPS URL with public IP should pass."""
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            validate_url("https://example.com/page")  # Should not raise

    def test_valid_http_url(self):
        """Valid HTTP URL with public IP should pass."""
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            validate_url("http://example.com/page")  # Should not raise

    def test_invalid_scheme_ftp(self):
        """FTP scheme should be blocked."""
        with pytest.raises(ValueError, match="Invalid URL scheme: ftp"):
            validate_url("ftp://example.com/file.txt")

    def test_invalid_scheme_file(self):
        """File scheme should be blocked."""
        with pytest.raises(ValueError, match="Invalid URL scheme: file"):
            validate_url("file:///etc/passwd")

    def test_invalid_scheme_javascript(self):
        """Javascript scheme should be blocked."""
        with pytest.raises(ValueError, match="Invalid URL scheme: javascript"):
            validate_url("javascript:alert(1)")

    def test_missing_hostname(self):
        """URL without hostname should be blocked."""
        with pytest.raises(ValueError, match="URL must have a hostname"):
            validate_url("https:///path")

    def test_private_ip_10_range(self):
        """10.x.x.x private range should be blocked."""
        with patch("socket.gethostbyname", return_value="10.0.0.1"):
            with pytest.raises(ValueError, match="private IP range"):
                validate_url("https://internal.example.com")

    def test_private_ip_172_range(self):
        """172.16-31.x.x private range should be blocked."""
        with patch("socket.gethostbyname", return_value="172.16.0.1"):
            with pytest.raises(ValueError, match="private IP range"):
                validate_url("https://internal.example.com")

    def test_private_ip_192_168_range(self):
        """192.168.x.x private range should be blocked."""
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            with pytest.raises(ValueError, match="private IP range"):
                validate_url("https://internal.example.com")

    def test_localhost_127_0_0_1(self):
        """127.0.0.1 loopback should be blocked."""
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            # Note: is_private catches 127.0.0.1 before is_loopback
            with pytest.raises(ValueError, match="Blocked.*127.0.0.1"):
                validate_url("https://localhost/admin")

    def test_localhost_name(self):
        """localhost hostname should be blocked."""
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="Blocked.*127.0.0.1"):
                validate_url("https://localhost")

    def test_link_local_address(self):
        """Link-local addresses (169.254.x.x) should be blocked."""
        with patch("socket.gethostbyname", return_value="169.254.1.1"):
            # Note: is_private catches link-local before is_link_local
            with pytest.raises(ValueError, match="Blocked.*169.254.1.1"):
                validate_url("https://link-local.example.com")

    def test_cloud_metadata_endpoint(self):
        """AWS/GCP/Azure metadata endpoint should be blocked."""
        with patch("socket.gethostbyname", return_value="169.254.169.254"):
            with pytest.raises(ValueError, match="Blocked.*169.254.169.254"):
                validate_url("http://169.254.169.254/latest/meta-data/")

    def test_unresolvable_hostname(self):
        """Unresolvable hostname should raise error."""
        import socket as sock

        with patch("socket.gethostbyname", side_effect=sock.gaierror):
            with pytest.raises(ValueError, match="Cannot resolve hostname"):
                validate_url("https://nonexistent.invalid.domain")

    def test_whitelisted_domain_slack_files(self):
        """files.slack.com should be allowed without IP check."""
        # No need to mock socket.gethostbyname - whitelist bypasses it
        validate_url("https://files.slack.com/files-pri/T123/file.pdf")

    def test_whitelisted_domain_slack_api(self):
        """api.slack.com should be allowed without IP check."""
        validate_url("https://api.slack.com/files/get")

    def test_whitelisted_domains_set(self):
        """Verify expected domains are in whitelist."""
        assert "files.slack.com" in WHITELISTED_DOMAINS
        assert "api.slack.com" in WHITELISTED_DOMAINS


class TestFetchUrlContentSSRF:
    """Tests for SSRF protection in fetch_url_content."""

    @pytest.mark.asyncio
    async def test_blocks_private_ip_initial_url(self):
        """Should block initial URL pointing to private IP."""
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            result = await fetch_url_content("https://internal.server.local/api")

        assert "error" in result
        assert "private IP range" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_localhost_initial_url(self):
        """Should block initial URL pointing to localhost."""
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            result = await fetch_url_content("http://localhost:8080/admin")

        assert "error" in result
        assert "127.0.0.1" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_file_scheme(self):
        """Should block file:// URLs."""
        result = await fetch_url_content("file:///etc/passwd")

        assert "error" in result
        assert "Invalid URL scheme" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_redirect_to_private_ip(self):
        """Should block redirect that leads to private IP."""
        # First URL is public, redirect goes to private
        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {"location": "http://192.168.1.1/internal"}

        with patch("socket.gethostbyname") as mock_dns:
            # First call for initial URL - public IP
            # Second call for redirect destination - private IP
            mock_dns.side_effect = ["93.184.216.34", "192.168.1.1"]

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                mock_client.return_value = mock_instance

                result = await fetch_url_content("https://evil.com/redirect")

        assert "error" in result
        assert "Blocked redirect" in result["error"]
        assert "private IP range" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_redirect_to_localhost(self):
        """Should block redirect that leads to localhost."""
        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {"location": "http://localhost/admin"}

        with patch("socket.gethostbyname") as mock_dns:
            mock_dns.side_effect = ["93.184.216.34", "127.0.0.1"]

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                mock_client.return_value = mock_instance

                result = await fetch_url_content("https://evil.com/redirect")

        assert "error" in result
        assert "Blocked redirect" in result["error"]
        assert "127.0.0.1" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_too_many_redirects(self):
        """Should block after too many redirects."""
        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {"location": "https://example.com/next"}

        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.return_value = mock_response
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                mock_client.return_value = mock_instance

                result = await fetch_url_content("https://example.com/start")

        assert "error" in result
        assert "Too many redirects" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_relative_redirect(self):
        """Should correctly handle relative redirect paths."""
        redirect_response = MagicMock()
        redirect_response.is_redirect = True
        redirect_response.headers = {"location": "/final/page"}

        final_response = MagicMock()
        final_response.is_redirect = False
        final_response.text = "<html><body>Content</body></html>"
        final_response.raise_for_status = MagicMock()

        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get.side_effect = [redirect_response, final_response]
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                mock_client.return_value = mock_instance

                with patch("trafilatura.extract", return_value="Extracted content"):
                    with patch("trafilatura.extract_metadata", return_value=None):
                        result = await fetch_url_content("https://example.com/start")

        assert "error" not in result
        assert result["url"] == "https://example.com/final/page"

    @pytest.mark.asyncio
    async def test_allows_whitelisted_slack_domain(self):
        """Should allow Slack file URLs without IP validation."""
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.text = "<html><body>File content</body></html>"
        mock_response.raise_for_status = MagicMock()

        # No DNS mock needed - whitelist bypasses DNS check
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("trafilatura.extract", return_value="File content"):
                with patch("trafilatura.extract_metadata", return_value=None):
                    result = await fetch_url_content(
                        "https://files.slack.com/files-pri/T123/document.pdf"
                    )

        assert "error" not in result
        assert result["text"] == "File content"


class TestSSRFEdgeCases:
    """Edge cases and bypass attempts."""

    def test_blocks_ipv4_mapped_ipv6(self):
        """Should block IPv4-mapped IPv6 addresses."""
        # ::ffff:127.0.0.1 is IPv4-mapped IPv6 for localhost
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            # Note: is_private catches 127.0.0.1
            with pytest.raises(ValueError, match="Blocked.*127.0.0.1"):
                validate_url("https://[::ffff:127.0.0.1]/admin")

    def test_blocks_decimal_ip(self):
        """Should resolve and block decimal IP notation."""
        # 2130706433 = 127.0.0.1 in decimal
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="Blocked.*127.0.0.1"):
                validate_url("http://2130706433/admin")

    def test_blocks_octal_ip(self):
        """Should resolve and block octal IP notation."""
        # 0177.0.0.1 = 127.0.0.1 in octal
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="Blocked.*127.0.0.1"):
                validate_url("http://0177.0.0.1/admin")

    def test_case_insensitive_whitelist(self):
        """Whitelist check should be case-insensitive."""
        # The validate_url function lowercases the hostname
        validate_url("https://FILES.SLACK.COM/file.pdf")
        validate_url("https://Files.Slack.Com/file.pdf")

    def test_blocks_metadata_via_dns_rebinding_setup(self):
        """DNS resolution happens at validation time, blocking known bad IPs."""
        # This tests the basic case - full DNS rebinding protection
        # would require additional measures (re-validation at connection time)
        with patch("socket.gethostbyname", return_value="169.254.169.254"):
            # Note: is_private catches link-local addresses
            with pytest.raises(ValueError, match="Blocked.*169.254.169.254"):
                validate_url("http://attacker.com/")
