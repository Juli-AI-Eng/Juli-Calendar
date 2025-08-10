"""Setup manager for handling Reclaim.ai + Nylas dual-provider setup."""
from typing import Dict, Any, Optional
import logging
from reclaim_sdk.client import ReclaimClient
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class SetupManager:
    """Manages setup and validation for the hybrid Reclaim + Nylas system."""
    
    def _is_valid_uuid(self, uuid_string: str) -> bool:
        """Check if a string is a valid UUID format."""
        import re
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, uuid_string))
    
    def get_instructions(self) -> Dict[str, Any]:
        """Get detailed setup instructions following Juli's best practices."""
        return {
            "type": "setup_instructions",
            "title": "Productivity Suite Setup Guide", 
            "estimated_time": "8 minutes",
            "steps": [
                {
                    "step": 1,
                    "title": "Get Your Reclaim.ai API Key",
                    "description": "Reclaim.ai manages your tasks and time blocking with AI-powered scheduling",
                    "actions": [
                        {
                            "type": "link",
                            "label": "Open Reclaim.ai Developer Settings",
                            "url": "https://app.reclaim.ai/settings/developer"
                        }
                    ],
                    "substeps": [
                        "Sign in to your Reclaim.ai account",
                        "Go to Settings → Developer (or use the link above)",
                        "Click 'Generate New API Key'",
                        "Copy the API key (starts with 'reclm_')",
                        "Keep this key secret - it's like a password!"
                    ],
                    "validation": {
                        "field": "reclaim_api_key",
                        "format": "starts with 'reclm_'",
                        "required": True
                    }
                },
                {
                    "step": 2,
                    "title": "Create Your Free Nylas Account",
                    "description": "Nylas provides universal calendar access (Google, Outlook, iCloud) - 5 free connections included!",
                    "actions": [
                        {
                            "type": "link", 
                            "label": "Open Nylas Signup",
                            "url": "https://dashboard-v3.nylas.com/register?utm_source=juli"
                        }
                    ],
                    "substeps": [
                        "Use the same email as your calendar account",
                        "No credit card required for free tier",
                        "Complete email verification if prompted"
                    ],
                    "tips": [
                        "⚠️ Critical: Use the SAME calendar account that Reclaim.ai uses",
                        "This ensures perfect synchronization between tasks and events"
                    ]
                },
                {
                    "step": 3,
                    "title": "Get Your Nylas API Key", 
                    "description": "After signing in to Nylas, get your API key",
                    "substeps": [
                        "Look for 'API Keys' in the left sidebar",
                        "Your API key should be visible (starts with 'nyk_')",
                        "Copy the API key",
                        "Keep this key secret!"
                    ],
                    "validation": {
                        "field": "nylas_api_key",
                        "format": "starts with 'nyk_'", 
                        "required": True
                    }
                },
                {
                    "step": 4,
                    "title": "Connect Your Calendar to Nylas",
                    "description": "Connect the SAME calendar account that Reclaim.ai uses",
                    "substeps": [
                        "Click 'Grants' in the Nylas sidebar",
                        "Click 'Add Test Grant' button (top right)",
                        "Choose your calendar provider (Google, Outlook, etc.)",
                        "⚠️ IMPORTANT: Use the SAME calendar as Reclaim.ai",
                        "Authorize Nylas to access your calendar",
                        "Copy the Grant ID that appears (UUID format)"
                    ],
                    "validation": {
                        "field": "nylas_grant_id",
                        "format": "UUID (8-4-4-4-12 characters)",
                        "required": True
                    },
                    "common_issues": [
                        {
                            "issue": "Can't find Grant ID",
                            "solution": "It's in the table under the 'ID' column after you connect"
                        },
                        {
                            "issue": "Authorization failed", 
                            "solution": "Make sure to allow all requested permissions"
                        },
                        {
                            "issue": "Wrong calendar account",
                            "solution": "Delete the grant and reconnect with the same account Reclaim.ai uses"
                        }
                    ]
                }
            ],
            "critical_requirements": [
                "Both Reclaim.ai and Nylas must use the SAME calendar account",
                "This ensures tasks and events don't conflict",
                "Juli will automatically verify calendar matching during setup"
            ],
            "next_step": {
                "description": "Once you have all three credentials, enter them in Juli to complete setup",
                "tips": [
                    "Juli will automatically verify both systems use the same calendar",
                    "Setup takes about 30 seconds after entering credentials",
                    "You'll see a success message when everything is connected"
                ]
            }
        }
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Validate individual credential format and presence."""
        missing_fields = []
        
        if not credentials.get("reclaim_api_key"):
            missing_fields.append("reclaim_api_key")
        if not credentials.get("nylas_api_key"):
            missing_fields.append("nylas_api_key")
        if not credentials.get("nylas_grant_id"):
            missing_fields.append("nylas_grant_id")
        
        if missing_fields:
            return {
                "validation_error": True,
                "missing_fields": missing_fields,
                "message": "Please provide all required credentials"
            }
        
        # Basic format validation
        if not credentials["reclaim_api_key"].startswith("reclm_"):
            return {
                "validation_error": True,
                "failed_system": "reclaim",
                "message": "Reclaim API key should start with 'reclm_'"
            }
        
        if not credentials["nylas_api_key"].startswith("nyk_"):
            return {
                "validation_error": True,
                "failed_system": "nylas",
                "message": "Nylas API key should start with 'nyk_'"
            }
        
        # UUID validation for grant ID
        if not self._is_valid_uuid(credentials["nylas_grant_id"]):
            return {
                "validation_error": True,
                "failed_system": "nylas",
                "message": "Nylas Grant ID should be a valid UUID"
            }
        
        return {"validation_error": False}
    
    def validate_complete_setup(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that both systems work and use the same calendar."""
        # First check basic validation
        basic_validation = self.validate_credentials(credentials)
        if basic_validation.get("validation_error"):
            return basic_validation
        
        # Step 1: Validate Reclaim.ai
        try:
            reclaim_client = ReclaimClient.configure(token=credentials['reclaim_api_key'])
            reclaim_user = reclaim_client.get('/api/users/current')
            # Try different fields where calendar email might be stored
            reclaim_calendar = (
                reclaim_user.get('calendar_email') or 
                reclaim_user.get('email') or
                reclaim_user.get('primary_email')
            )
            logger.info(f"Reclaim calendar: {reclaim_calendar}")
            
            if not reclaim_calendar:
                logger.error("No email found in Reclaim user data")
                return {
                    "validation_error": True,
                    "failed_system": "reclaim",
                    "message": "Could not determine calendar email from Reclaim.ai",
                    "fix": "Please contact support - unable to retrieve calendar information"
                }
        except Exception as e:
            logger.error(f"Reclaim validation error: {e}")
            return {
                "validation_error": True,
                "failed_system": "reclaim",
                "message": "Invalid Reclaim.ai API key",
                "fix": "Double-check your API key from https://app.reclaim.ai/settings/developer"
            }
        
        # Step 2: Validate Nylas
        try:
            nylas_client = NylasClient(
                api_key=credentials['nylas_api_key'],
                api_uri="https://api.us.nylas.com"  # Default to US, could be made configurable
            )
            grant = nylas_client.grants.find(grant_id=credentials['nylas_grant_id'])
            nylas_calendar = grant.data.email
            logger.info(f"Nylas calendar: {nylas_calendar}")
        except Exception as e:
            logger.error(f"Nylas validation error: {e}")
            return {
                "validation_error": True,
                "failed_system": "nylas",
                "message": "Invalid Nylas credentials",
                "fix": "Check your API key and Grant ID from Nylas dashboard"
            }
        
        # Step 3: Verify Same Calendar Account
        if reclaim_calendar.lower() != nylas_calendar.lower():
            return {
                "validation_error": True,
                "calendar_mismatch": True,
                "reclaim_calendar": reclaim_calendar,
                "nylas_calendar": nylas_calendar,
                "message": "⚠️ Calendar account mismatch!",
                "fix": "Both systems must use the same calendar account. Please reconnect one of them.",
                "instructions": [
                    f"Reclaim.ai is connected to: {reclaim_calendar}",
                    f"Nylas is connected to: {nylas_calendar}",
                    "Go to the system with the wrong account and reconnect it",
                    "Make sure both use the same calendar account"
                ]
            }
        
        # Step 4: Success!
        return {
            "setup_complete": True,
            "calendar_email": reclaim_calendar,
            "calendar_provider": grant.data.provider,
            "credentials_to_store": {
                "reclaim_api_key": credentials['reclaim_api_key'],
                "nylas_api_key": credentials['nylas_api_key'],
                "nylas_grant_id": credentials['nylas_grant_id']
            },
            "capabilities": [
                "✅ Task management via Reclaim.ai",
                "✅ Calendar event management via Nylas",
                "✅ Universal calendar access (Google, Outlook, iCloud)", 
                "✅ Intelligent AI routing between systems",
                "✅ Time blocking and productivity optimization",
                f"✅ Synchronized with {reclaim_calendar}"
            ],
            "message": f"🎉 Your hybrid productivity suite is ready! Both systems are connected to {reclaim_calendar}"
        }