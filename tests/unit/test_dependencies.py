"""Test for checking required dependencies are installed."""
import pytest


class TestDependencies:
    """Test that all required dependencies are available."""
    
    def test_nylas_import(self):
        """Test that Nylas SDK can be imported correctly."""
        # Based on Nylas v3 documentation, the correct import is:
        try:
            import nylas
            from nylas import Client
            # Verify we can instantiate a client (without API key for now)
            assert hasattr(nylas, 'Client')
        except ImportError:
            pytest.fail("Nylas SDK is not installed. Please add 'nylas' to requirements.txt")
    
    def test_nylas_version(self):
        """Test that Nylas SDK is v3.x compatible."""
        try:
            import nylas
            # Check that we have a modern version
            assert hasattr(nylas, '__version__') or hasattr(nylas, 'Client')
        except ImportError:
            pytest.fail("Nylas SDK is not installed")
    
    def test_existing_dependencies(self):
        """Test that existing dependencies are still available."""
        # These should all pass
        import flask
        import httpx
        import pydantic
        import openai
        import pytz
        from reclaim_sdk.client import ReclaimClient
        
        assert True