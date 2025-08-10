"""Tests for SetupManager class - TDD RED phase."""
import pytest
from unittest.mock import Mock, patch
import json


class TestSetupManager:
    """Test the SetupManager for handling dual-provider setup."""
    
    def test_setup_manager_import(self):
        """Test that SetupManager can be imported - RED phase."""
        try:
            from src.setup.setup_manager import SetupManager
            assert True
        except ImportError:
            pytest.fail("SetupManager not found. Need to create src/setup/setup_manager.py")
    
    def test_get_instructions_returns_correct_format(self):
        """Test that get_instructions returns proper setup instructions."""
        try:
            from src.setup.setup_manager import SetupManager
            manager = SetupManager()
            
            result = manager.get_instructions()
            
            # Check response type
            assert result["type"] == "setup_instructions"
            assert "title" in result
            assert "estimated_time" in result
            assert "steps" in result
            assert len(result["steps"]) == 4  # Reclaim + 3 Nylas steps
            
            # Check first step (Reclaim)
            reclaim_step = result["steps"][0]
            assert reclaim_step["title"] == "Get Your Reclaim.ai API Key"
            assert any(action["url"] == "https://app.reclaim.ai/settings/developer" 
                      for action in reclaim_step["actions"])
            
            # Check Nylas steps
            nylas_steps = result["steps"][1:]
            assert any("Nylas" in step["title"] for step in nylas_steps)
            
        except ImportError:
            pytest.skip("SetupManager not implemented yet")
    
    def test_validate_credentials_missing_fields(self):
        """Test validation with missing credentials."""
        try:
            from src.setup.setup_manager import SetupManager
            manager = SetupManager()
            
            # Test with no credentials
            result = manager.validate_credentials({})
            assert result["validation_error"] is True
            assert "missing_fields" in result
            
            # Test with only Reclaim
            result = manager.validate_credentials({"reclaim_api_key": "test"})
            assert result["validation_error"] is True
            assert "nylas" in result.get("failed_system", "") or "missing_fields" in result
            
        except ImportError:
            pytest.skip("SetupManager not implemented yet")
    
    @patch('src.setup.setup_manager.NylasClient')
    @patch('src.setup.setup_manager.ReclaimClient')
    def test_validate_credentials_success(self, mock_reclaim, mock_nylas):
        """Test successful credential validation."""
        try:
            from src.setup.setup_manager import SetupManager
            manager = SetupManager()
            
            # Mock Reclaim response
            mock_reclaim_instance = Mock()
            mock_reclaim_instance.get.return_value = {
                "email": "user@example.com"
            }
            mock_reclaim.configure.return_value = mock_reclaim_instance
            
            # Mock Nylas response
            mock_nylas_instance = Mock()
            mock_grant = Mock()
            mock_grant.data.email = "user@example.com"
            mock_grant.data.provider = "google"
            mock_nylas_instance.grants.find.return_value = mock_grant
            mock_nylas.return_value = mock_nylas_instance
            
            # Test validation
            credentials = {
                "reclaim_api_key": "reclm_test123",
                "nylas_api_key": "nyk_test123",
                "nylas_grant_id": "12345678-1234-1234-1234-123456789012"
            }
            
            result = manager.validate_complete_setup(credentials)
            
            assert result["setup_complete"] is True
            assert result["calendar_email"] == "user@example.com"
            assert "credentials_to_store" in result
            
        except ImportError:
            pytest.skip("SetupManager not implemented yet")
    
    @patch('src.setup.setup_manager.NylasClient')
    @patch('src.setup.setup_manager.ReclaimClient')
    def test_validate_credentials_calendar_mismatch(self, mock_reclaim, mock_nylas):
        """Test validation fails when calendar accounts don't match."""
        try:
            from src.setup.setup_manager import SetupManager
            manager = SetupManager()
            
            # Mock Reclaim with one email
            mock_reclaim_instance = Mock()
            mock_reclaim_instance.get.return_value = {
                "email": "user@example.com"
            }
            mock_reclaim.configure.return_value = mock_reclaim_instance
            
            # Mock Nylas with different email
            mock_nylas_instance = Mock()
            mock_grant = Mock()
            mock_grant.data.email = "different@example.com"
            mock_grant.data.provider = "google"
            mock_nylas_instance.grants.find.return_value = mock_grant
            mock_nylas.return_value = mock_nylas_instance
            
            credentials = {
                "reclaim_api_key": "reclm_test123",
                "nylas_api_key": "nyk_test123",
                "nylas_grant_id": "12345678-1234-1234-1234-123456789012"
            }
            
            result = manager.validate_complete_setup(credentials)
            
            assert result.get("validation_error") is True
            assert result.get("calendar_mismatch") is True
            assert result["reclaim_calendar"] == "user@example.com"
            assert result["nylas_calendar"] == "different@example.com"
            
        except ImportError:
            pytest.skip("SetupManager not implemented yet")
    
    def test_uuid_validation(self):
        """Test UUID validation helper method."""
        from src.setup.setup_manager import SetupManager
        manager = SetupManager()
        
        # Valid UUIDs
        assert manager._is_valid_uuid("12345678-1234-1234-1234-123456789012") is True
        assert manager._is_valid_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True
        
        # Invalid UUIDs
        assert manager._is_valid_uuid("not-a-uuid") is False
        assert manager._is_valid_uuid("12345678-1234-1234-1234") is False
        assert manager._is_valid_uuid("12345678123412341234123456789012") is False
        assert manager._is_valid_uuid("") is False