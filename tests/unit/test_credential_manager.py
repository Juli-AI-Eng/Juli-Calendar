"""Tests for CredentialManager - handling dual provider credentials."""
import pytest
from unittest.mock import Mock, patch


class TestCredentialManager:
    """Test the CredentialManager for extracting and managing dual credentials."""
    
    def test_credential_manager_import(self):
        """Test that CredentialManager can be imported - RED phase."""
        try:
            from src.auth.credential_manager import CredentialManager
            assert True
        except ImportError:
            pytest.fail("CredentialManager not found. Need to create src/auth/credential_manager.py")
    
    def test_extract_reclaim_credentials(self):
        """Test extracting Reclaim API key from headers."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            # Test with proper header
            headers = {
                'X-User-Credential-RECLAIM_API_KEY': 'reclm_test123',
                'Content-Type': 'application/json'
            }
            
            creds = manager.extract_credentials(headers)
            assert creds['reclaim_api_key'] == 'reclm_test123'
            
            # Test with lowercase header
            headers_lower = {
                'x-user-credential-reclaim_api_key': 'reclm_test456',
            }
            
            creds = manager.extract_credentials(headers_lower)
            assert creds['reclaim_api_key'] == 'reclm_test456'
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")
    
    def test_extract_nylas_credentials(self):
        """Test extracting Nylas credentials from headers."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            headers = {
                'X-User-Credential-NYLAS_API_KEY': 'nyk_test123',
                'X-User-Credential-NYLAS_GRANT_ID': '12345678-1234-1234-1234-123456789012'
            }
            
            creds = manager.extract_credentials(headers)
            assert creds['nylas_api_key'] == 'nyk_test123'
            assert creds['nylas_grant_id'] == '12345678-1234-1234-1234-123456789012'
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")
    
    def test_extract_both_providers(self):
        """Test extracting credentials for both providers."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            headers = {
                'X-User-Credential-RECLAIM_API_KEY': 'reclm_test123',
                'X-User-Credential-NYLAS_API_KEY': 'nyk_test123',
                'X-User-Credential-NYLAS_GRANT_ID': '12345678-1234-1234-1234-123456789012',
                'X-Other-Header': 'ignored'
            }
            
            creds = manager.extract_credentials(headers)
            assert creds['reclaim_api_key'] == 'reclm_test123'
            assert creds['nylas_api_key'] == 'nyk_test123'
            assert creds['nylas_grant_id'] == '12345678-1234-1234-1234-123456789012'
            assert 'X-Other-Header' not in creds
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")
    
    def test_is_setup_complete(self):
        """Test checking if setup is complete."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            # No credentials
            assert manager.is_setup_complete({}) is False
            
            # Only Reclaim
            assert manager.is_setup_complete({'reclaim_api_key': 'test'}) is False
            
            # Only Nylas API key
            assert manager.is_setup_complete({'nylas_api_key': 'test'}) is False
            
            # Nylas without grant ID
            assert manager.is_setup_complete({
                'reclaim_api_key': 'test',
                'nylas_api_key': 'test'
            }) is False
            
            # All credentials present
            assert manager.is_setup_complete({
                'reclaim_api_key': 'reclm_test',
                'nylas_api_key': 'nyk_test',
                'nylas_grant_id': '12345678-1234-1234-1234-123456789012'
            }) is True
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")
    
    @patch('src.auth.credential_manager.NylasClient')
    @patch('src.auth.credential_manager.ReclaimClient')
    def test_create_clients(self, mock_reclaim, mock_nylas):
        """Test creating API clients from credentials."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            credentials = {
                'reclaim_api_key': 'reclm_test123',
                'nylas_api_key': 'nyk_test123',
                'nylas_grant_id': '12345678-1234-1234-1234-123456789012'
            }
            
            # Mock client instances
            mock_reclaim_instance = Mock()
            mock_nylas_instance = Mock()
            mock_reclaim.configure.return_value = mock_reclaim_instance
            mock_nylas.return_value = mock_nylas_instance
            
            # Create clients
            clients = manager.create_clients(credentials)
            
            assert 'reclaim' in clients
            assert 'nylas' in clients
            assert clients['reclaim'] == mock_reclaim_instance
            assert clients['nylas'] == mock_nylas_instance
            
            # Verify proper configuration
            mock_reclaim.configure.assert_called_once_with(token='reclm_test123')
            mock_nylas.assert_called_once_with(
                api_key='nyk_test123',
                api_uri='https://api.us.nylas.com'
            )
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")
    
    def test_create_clients_missing_credentials(self):
        """Test error handling when credentials are missing."""
        try:
            from src.auth.credential_manager import CredentialManager
            manager = CredentialManager()
            
            # Should raise exception with missing credentials
            with pytest.raises(ValueError) as exc_info:
                manager.create_clients({'reclaim_api_key': 'test'})
            
            assert "Missing required credentials" in str(exc_info.value)
            
        except ImportError:
            pytest.skip("CredentialManager not implemented yet")