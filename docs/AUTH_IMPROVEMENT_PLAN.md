# Authentication Improvement Plan for Juli Calendar Agent

## Executive Summary

This document outlines a comprehensive plan to improve the authentication experience for the Juli Calendar Agent. Currently, users must manually copy API keys for both Reclaim.ai and Nylas, which creates friction in the onboarding process. This plan proposes implementing OAuth for Nylas (similar to Juli-Email) and a streamlined manual process for Reclaim.ai (which lacks OAuth support).

## Current State Analysis

### Pain Points
1. **Manual API Key Entry**: Users must navigate to external websites, generate keys, and copy-paste them
2. **Technical Complexity**: Non-technical users may find the process intimidating
3. **Error-Prone**: Manual copying can lead to errors (extra spaces, incomplete copying)
4. **No Immediate Validation**: Users don't know if their keys work until they try to use features

### Current Flow
- Users receive text instructions to manually obtain:
  - Reclaim.ai API key from `https://app.reclaim.ai/settings/developer`
  - Nylas Grant ID (currently manual, but OAuth is available)
- Keys are injected via headers in each request (stateless design)

## Proposed Solution Architecture

### 1. Nylas OAuth Implementation (Hosted Auth Flow)

#### Technical Architecture
Following the successful pattern from Juli-Email, implement a redirect-based OAuth flow:

```
User → Juli Brain → Calendar Agent → Nylas Auth → User Consent → Callback → Juli Brain
```

#### Implementation Components

**A. Discovery Endpoint Enhancement**
```python
# /.well-known/a2a-credentials.json
{
  "credentials": [
    {
      "key": "NYLAS_GRANT_ID",
      "display_name": "Calendar Account",
      "sensitive": true,
      "flows": [
        {
          "type": "hosted_auth",
          "connect_url": "/setup/nylas/connect",
          "callback": "/api/nylas/callback",
          "provider": "nylas",
          "scopes": {
            "google": ["calendar", "calendar.events"],
            "microsoft": ["Calendars.ReadWrite", "User.Read"]
          }
        }
      ]
    },
    {
      "key": "RECLAIM_API_KEY",
      "display_name": "Reclaim.ai API Key",
      "sensitive": true,
      "flows": [
        {
          "type": "manual_with_validation",
          "instructions_url": "/setup/reclaim/instructions",
          "validation_url": "/setup/reclaim/validate",
          "provider": "reclaim"
        }
      ]
    }
  ]
}
```

**B. OAuth Flow Endpoints**
```python
# New endpoints in src/server.py

@app.route("/setup/nylas/connect", methods=["GET"])
async def nylas_connect():
    """Initiate Nylas OAuth flow"""
    redirect_uri = request.args.get("redirect_uri")  # Juli Brain's callback
    state = request.args.get("state")  # CSRF protection
    
    # Build Nylas auth URL with agent's API key
    auth_url = build_nylas_auth_url(
        client_id=os.getenv("NYLAS_CLIENT_ID"),
        redirect_uri=f"{BASE_URL}/api/nylas/callback",
        state=state,
        scopes=["calendar", "email", "contacts"]
    )
    
    # Store state temporarily for validation (use Redis/cache in production)
    cache_state(state, redirect_uri)
    
    return redirect(auth_url)

@app.route("/api/nylas/callback", methods=["GET"])
async def nylas_callback():
    """Handle Nylas OAuth callback"""
    code = request.args.get("code")
    state = request.args.get("state")
    
    # Validate state
    original_redirect = validate_and_get_redirect(state)
    
    # Exchange code for grant_id
    grant_data = exchange_code_for_grant(code)
    
    # Redirect back to Juli Brain with grant_id
    return redirect(f"{original_redirect}?grant_id={grant_data['grant_id']}&email={grant_data['email']}")
```

### 2. Reclaim.ai Authentication Enhancement

Since Reclaim.ai doesn't support OAuth, we'll optimize the manual process:

#### A. Interactive Setup Wizard
```python
@app.route("/setup/reclaim/instructions", methods=["GET"])
def reclaim_instructions():
    """Provide interactive setup instructions"""
    return jsonify({
        "type": "guided_setup",
        "provider": "reclaim",
        "steps": [
            {
                "order": 1,
                "action": "open_link",
                "url": "https://app.reclaim.ai/settings/developer",
                "instruction": "Click to open Reclaim.ai Developer Settings",
                "visual_guide": "/static/images/reclaim-step1.png"
            },
            {
                "order": 2,
                "action": "generate_key",
                "instruction": "Click 'Generate New API Key'",
                "visual_guide": "/static/images/reclaim-step2.png"
            },
            {
                "order": 3,
                "action": "copy_key",
                "instruction": "Name it 'Juli Integration' and copy the key",
                "validation_hint": "Key should start with 'reclm_'"
            },
            {
                "order": 4,
                "action": "paste_and_validate",
                "instruction": "Paste your key below",
                "validation_endpoint": "/setup/reclaim/validate"
            }
        ]
    })
```

#### B. Real-time Validation
```python
@app.route("/setup/reclaim/validate", methods=["POST"])
async def validate_reclaim():
    """Validate Reclaim API key in real-time"""
    data = request.get_json()
    api_key = data.get("reclaim_api_key")
    
    # Basic format validation
    if not api_key or not api_key.startswith("reclm_"):
        return jsonify({
            "valid": False,
            "error": "Invalid key format. Should start with 'reclm_'"
        }), 400
    
    # Test API connection
    try:
        client = ReclaimClient.configure(token=api_key)
        user_info = client.get('/api/users/current')
        
        return jsonify({
            "valid": True,
            "user_email": user_info.get("email"),
            "calendar_email": user_info.get("calendar_email"),
            "message": "Successfully connected to Reclaim.ai!"
        })
    except Exception as e:
        return jsonify({
            "valid": False,
            "error": "Could not connect to Reclaim.ai. Please check your API key."
        }), 400
```

### 3. Unified Setup Experience

#### Setup Flow UI Components

**A. Initial Setup Screen**
```javascript
// Juli Brain UI Component
<SetupWizard>
  <CalendarSetup>
    <h2>Connect Your Calendar</h2>
    <p>Sync with Google, Outlook, or iCloud calendars</p>
    <OAuthButton 
      provider="nylas"
      onClick={initiateNylasOAuth}
      text="Connect Calendar"
      icon="calendar"
    />
    <StatusIndicator connected={nylasConnected} />
  </CalendarSetup>
  
  <TaskSetup>
    <h2>Connect Task Management</h2>
    <p>AI-powered scheduling with Reclaim.ai</p>
    <GuidedSetup
      provider="reclaim"
      onValidate={validateReclaimKey}
      deepLink="https://app.reclaim.ai/settings/developer"
    >
      <APIKeyInput 
        placeholder="Paste your Reclaim.ai API key"
        pattern="^reclm_.*"
        onPaste={autoValidate}
      />
    </GuidedSetup>
    <StatusIndicator connected={reclaimConnected} />
  </TaskSetup>
</SetupWizard>
```

**B. Progressive Validation**
```javascript
// Real-time validation as user types/pastes
function autoValidate(apiKey) {
  // Immediate format check
  if (!apiKey.startsWith('reclm_')) {
    showError('Key should start with "reclm_"');
    return;
  }
  
  // Debounced API validation
  debounce(() => {
    validateWithServer(apiKey).then(result => {
      if (result.valid) {
        showSuccess('Connected to Reclaim.ai!');
        checkCalendarSync(result.calendar_email);
      } else {
        showError(result.error);
      }
    });
  }, 500);
}
```

## Security Considerations

### 1. OAuth Security
- **State Parameter**: Use cryptographically secure random state for CSRF protection
  - Store in Redis with TTL (10 minutes max)
  - Use `secrets.token_urlsafe(32)` for generation
  - Validate and immediately invalidate after use
- **HTTPS Only**: All OAuth redirects must use HTTPS in production
- **Token Storage**: Agent remains stateless; Juli Brain stores grant_id securely
- **Scope Limitation**: Request only necessary scopes (calendar, not full email access)
- **Grant Lifecycle Management**:
  - Juli Brain handles refresh token rotation if needed
  - Agent returns specific error codes for expired/revoked grants
  - Automatic re-authentication triggers in Juli Brain

### 2. API Key Security
- **Transport Security**: Always use HTTPS for API key transmission
- **No Client Storage**: Keys are never stored in browser localStorage/cookies
- **Server Validation**: All validation happens server-side
- **Rate Limiting**: Implement rate limiting on validation endpoints

### 3. Credential Injection
- **Per-Request Injection**: Credentials injected fresh in each request
- **No Caching**: Agent doesn't cache or store user credentials
- **Audit Logging**: Log all credential validation attempts

## Implementation Architecture

### Module Organization
```
src/
├── auth/
│   ├── __init__.py
│   ├── credential_manager.py  # Existing credential extraction
│   ├── nylas_oauth.py        # NEW: Nylas OAuth flow handlers
│   └── state_manager.py       # NEW: Redis-based state management
├── setup/
│   ├── __init__.py
│   ├── setup_manager.py      # Enhanced with OAuth methods
│   └── reclaim_validator.py  # NEW: Dedicated Reclaim validation
└── server.py                  # Route registration only
```

## Implementation Timeline

### Phase 1: Nylas OAuth (Week 1-2)
1. Implement OAuth flow endpoints in `src/auth/nylas_oauth.py`
2. Add Redis-based state management with Flask-Session
3. Create callback handling logic with proper error recovery
4. Test with multiple calendar providers (Google, Outlook, iCloud)

### Phase 2: Reclaim Enhancement (Week 2-3)
1. Build instruction endpoint with visual guides
2. Implement real-time validation
3. Create deep-linking flow
4. Add clipboard detection for auto-validation

### Phase 3: UI Integration (Week 3-4)
1. Update Juli Brain UI components
2. Add progress indicators
3. Implement error recovery flows
4. Add calendar synchronization check

### Phase 4: Testing & Polish (Week 4-5)
1. End-to-end testing of both flows
2. Error handling improvements
3. Documentation updates
4. Performance optimization

## Success Metrics

### User Experience Metrics
- **Setup Completion Rate**: Target >90% (from current ~70%)
- **Time to Complete Setup**: Target <3 minutes (from current ~10 minutes)
- **Error Rate**: Target <5% validation failures
- **Support Tickets**: Reduce auth-related tickets by 80%

### Technical Metrics
- **OAuth Success Rate**: >95% successful callbacks
- **Validation Response Time**: <500ms for API key validation
- **State Validation Success**: 100% CSRF protection
- **Concurrent Setup Support**: Handle 100+ simultaneous setups

## Migration Strategy

### Backward Compatibility
1. Maintain existing manual credential injection for current users
2. Support both old (manual) and new (OAuth) Nylas authentication
3. Gradual migration with user prompts to upgrade

### Rollout Plan
1. **Alpha**: Internal testing with Juli team
2. **Beta**: 10% of new users get new flow
3. **Gradual Rollout**: Increase to 50%, then 100%
4. **Migration Campaign**: Prompt existing users to re-authenticate

## Alternative Approaches Considered

### 1. Browser Extension for Reclaim
- **Pros**: Could auto-extract API key from Reclaim.ai page
- **Cons**: Requires additional installation step, security concerns

### 2. Partnership with Reclaim for OAuth
- **Pros**: Best user experience
- **Cons**: Requires Reclaim.ai to implement OAuth (not currently available)

### 3. Proxy Authentication Service
- **Pros**: Could manage keys centrally
- **Cons**: Single point of failure, additional infrastructure

## Conclusion

This authentication improvement plan addresses the current pain points while maintaining security and the stateless design of the Juli Calendar Agent. The Nylas OAuth implementation provides a seamless experience for calendar connection, while the enhanced Reclaim.ai flow minimizes friction in the manual process. Together, these improvements will significantly enhance user onboarding and reduce support burden.

## Appendix

### A. Required Environment Variables
```bash
# Nylas OAuth (Agent-side)
NYLAS_API_KEY=nylas_api_key_here
NYLAS_CLIENT_ID=nylas_client_id_here
NYLAS_CLIENT_SECRET=nylas_client_secret_here
NYLAS_API_URI=https://api.us.nylas.com

# OAuth Configuration
OAUTH_STATE_TTL=600  # State expiry in seconds
REDIS_URL=redis://localhost:6379  # For state storage
SESSION_TYPE=redis  # Flask-Session backend
SESSION_PERMANENT=false
SESSION_USE_SIGNER=true
SESSION_KEY_PREFIX=juli_calendar:

# Security
REQUIRE_HTTPS=true  # Force HTTPS in production
RATE_LIMIT_VALIDATION=10  # Max validations per minute
RATE_LIMIT_WINDOW=60  # Rate limit window in seconds
```

### B. API Endpoints Summary
```yaml
OAuth Endpoints:
  - GET /setup/nylas/connect: Initiate Nylas OAuth
  - GET /api/nylas/callback: Handle Nylas callback
  
Manual Setup Endpoints:
  - GET /setup/reclaim/instructions: Get guided instructions
  - POST /setup/reclaim/validate: Validate Reclaim API key
  
Discovery:
  - GET /.well-known/a2a-credentials.json: Credential flow discovery
```

### C. Error Codes and Recovery
```json
{
  "AUTH001": {
    "message": "Invalid state parameter",
    "recovery": "Restart OAuth flow with new state",
    "user_message": "Session expired. Please try connecting again."
  },
  "AUTH002": {
    "message": "OAuth callback failed",
    "recovery": "Display error and retry button",
    "user_message": "Connection failed. Please try again or contact support."
  },
  "AUTH003": {
    "message": "Invalid API key format",
    "recovery": "Show format hint and example",
    "user_message": "Invalid key format. Keys should start with 'reclm_'"
  },
  "AUTH004": {
    "message": "API validation failed",
    "recovery": "Check connection and retry",
    "user_message": "Could not connect to Reclaim.ai. Please verify your API key."
  },
  "AUTH005": {
    "message": "Calendar mismatch detected",
    "recovery": "Prompt to use same calendar",
    "user_message": "Please ensure both services use the same calendar account."
  },
  "AUTH006": {
    "message": "Rate limit exceeded",
    "recovery": "Wait and retry with backoff",
    "user_message": "Too many attempts. Please wait a moment and try again."
  },
  "AUTH007": {
    "message": "Grant expired or revoked",
    "recovery": "Trigger re-authentication",
    "user_message": "Calendar access expired. Please reconnect your calendar."
  }
}
```

### D. Edge Case Handling

#### User Flow Interruptions
- **Browser closed during OAuth**: State expires after 10 minutes, user can safely restart
- **Network failure during callback**: Error page with retry button
- **Multiple tabs/windows**: State validation prevents CSRF attacks
- **Back button usage**: Detect and guide user to proper flow

#### Data Migration for Existing Users
```python
# Migration strategy for users with existing manual credentials
class CredentialMigration:
    def should_prompt_for_oauth(self, user):
        # Check if user has manual Nylas credentials
        if user.has_manual_nylas_key and not user.has_oauth_grant:
            return True
        return False
    
    def migrate_to_oauth(self, user):
        # Soft migration - keep old credentials working
        # while prompting for OAuth upgrade
        return {
            "migration_type": "soft",
            "keep_legacy": True,
            "prompt_frequency": "weekly",
            "benefits_message": "Upgrade for automatic token refresh and better security"
        }
```