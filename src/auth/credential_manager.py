"""Credential manager for handling dual provider authentication."""
from typing import Dict, Any, Optional
import logging
from reclaim_sdk.client import ReclaimClient
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages credential extraction and client creation for dual providers."""
    
    # Required credential fields
    REQUIRED_FIELDS = ['reclaim_api_key', 'nylas_api_key', 'nylas_grant_id']
    
    # Header mapping
    HEADER_MAPPING = {
        'x-user-credential-reclaim_api_key': 'reclaim_api_key',
        'x-user-credential-nylas_api_key': 'nylas_api_key',
        'x-user-credential-nylas_grant_id': 'nylas_grant_id'
    }
    
    def extract_credentials(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Extract Juli credentials from request headers.
        
        Headers come in the format:
        X-User-Credential-RECLAIM_API_KEY: reclm_xxx
        X-User-Credential-NYLAS_API_KEY: nyk_xxx
        X-User-Credential-NYLAS_GRANT_ID: uuid
        """
        credentials = {}
        
        # Convert all headers to lowercase for case-insensitive matching
        for key, value in headers.items():
            lower_key = key.lower()
            
            if lower_key in self.HEADER_MAPPING:
                credentials[self.HEADER_MAPPING[lower_key]] = value
        
        logger.debug(f"Extracted credentials for: {list(credentials.keys())}")
        return credentials
    
    def is_setup_complete(self, credentials: Dict[str, str]) -> bool:
        """Check if all required credentials are present."""
        return all(field in credentials for field in self.REQUIRED_FIELDS)
    
    def create_clients(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Create API clients from credentials.
        
        Returns dict with 'reclaim' and 'nylas' client instances.
        Raises ValueError if credentials are incomplete.
        """
        if not self.is_setup_complete(credentials):
            missing = [field for field in self.REQUIRED_FIELDS if field not in credentials]
            raise ValueError(f"Missing required credentials: {', '.join(missing)}")
        
        # Create Reclaim client
        reclaim_client = ReclaimClient.configure(token=credentials['reclaim_api_key'])
        
        # Create Nylas client
        nylas_client = NylasClient(
            api_key=credentials['nylas_api_key'],
            api_uri='https://api.us.nylas.com'  # Default to US region
        )
        
        return {
            'reclaim': reclaim_client,
            'nylas': nylas_client,
            'grant_id': credentials['nylas_grant_id']  # Store grant ID for later use
        }
    
    def get_setup_status(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Get detailed setup status for user feedback."""
        status = {
            'setup_complete': False,
            'reclaim_connected': 'reclaim_api_key' in credentials,
            'nylas_connected': 'nylas_api_key' in credentials and 'nylas_grant_id' in credentials,
            'missing_providers': []
        }
        
        if not status['reclaim_connected']:
            status['missing_providers'].append('Reclaim.ai')
        
        if not status['nylas_connected']:
            status['missing_providers'].append('Nylas Calendar')
        
        status['setup_complete'] = self.is_setup_complete(credentials)
        
        return status