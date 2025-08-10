"""Unit tests for server helper functions."""
import pytest
from src.server import extract_credential, extract_all_credentials


class TestExtractCredential:
    """Unit tests for extract_credential function."""
    
    def test_extract_credential_exact_match(self):
        """Should extract credential with exact header match."""
        headers = {"X-User-Credential-RECLAIM_API_KEY": "test_key"}
        result = extract_credential(headers, "RECLAIM_API_KEY")
        assert result == "test_key"
    
    def test_extract_credential_hyphenated(self):
        """Should extract credential with hyphenated header."""
        headers = {"X-User-Credential-Reclaim-Api-Key": "test_key"}
        result = extract_credential(headers, "RECLAIM_API_KEY")
        assert result == "test_key"
    
    def test_extract_credential_lowercase(self):
        """Should extract credential with lowercase header."""
        headers = {"x-user-credential-reclaim_api_key": "test_key"}
        result = extract_credential(headers, "RECLAIM_API_KEY")
        assert result == "test_key"
    
    def test_extract_credential_not_found(self):
        """Should return None when credential not found."""
        headers = {"X-Some-Other-Header": "value"}
        result = extract_credential(headers, "RECLAIM_API_KEY")
        assert result is None
    
    def test_extract_credential_empty_headers(self):
        """Should return None for empty headers."""
        result = extract_credential({}, "RECLAIM_API_KEY")
        assert result is None


class TestExtractAllCredentials:
    """Unit tests for extract_all_credentials function."""
    
    def test_extract_single_credential(self):
        """Should extract a single credential."""
        headers = {"X-User-Credential-API_KEY": "test_key"}
        result = extract_all_credentials(headers)
        assert "API_KEY" in result
        assert result["API_KEY"] == "test_key"
    
    def test_extract_multiple_credentials(self):
        """Should extract multiple credentials."""
        headers = {
            "X-User-Credential-API_KEY": "key1",
            "X-User-Credential-WORKSPACE_ID": "ws123",
            "X-Other-Header": "ignored"
        }
        result = extract_all_credentials(headers)
        assert len(result) == 2
        assert result["API_KEY"] == "key1"
        assert result["WORKSPACE_ID"] == "ws123"
    
    def test_extract_hyphenated_credentials(self):
        """Should extract credentials with hyphens in header."""
        headers = {"X-User-Credential-Reclaim-Api-Key": "test_key"}
        result = extract_all_credentials(headers)
        assert "Reclaim-Api-Key" in result
        assert result["Reclaim-Api-Key"] == "test_key"
    
    def test_extract_no_credentials(self):
        """Should return empty dict when no credentials found."""
        headers = {"Content-Type": "application/json"}
        result = extract_all_credentials(headers)
        assert result == {}
    
    def test_extract_mixed_case_headers(self):
        """Should handle mixed case headers."""
        headers = {
            "x-user-credential-api_key": "key1",
            "X-USER-CREDENTIAL-WORKSPACE": "ws123"
        }
        result = extract_all_credentials(headers)
        # Should extract at least one credential
        assert len(result) > 0