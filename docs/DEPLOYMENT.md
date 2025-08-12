# Production Deployment Guide

This guide covers the differences between testing and production configurations for the Juli Calendar Agent.

## Environment Configuration Differences

### Production `.env` vs Test `.env.test`

| Purpose | File | Contains | Usage |
|---------|------|----------|-------|
| **Production** | `.env` | Server config only | Runtime server configuration |
| **Testing** | `.env.test` | Real API credentials | E2E testing with real APIs |

### Key Differences

#### Production `.env`:
```bash
# Server-level configuration
OPENAI_API_KEY=your_openai_api_key_here
PORT=5000
HOST=0.0.0.0
FLASK_ENV=production
DEBUG=false
SECRET_KEY=your_secret_key_here
LOG_LEVEL=INFO
```

**What it does NOT contain:**
- ❌ Reclaim API keys
- ❌ Nylas API keys  
- ❌ User credentials

**Why:** In production, user credentials are injected per-request via HTTP headers from Juli, not stored in server environment.

#### Test `.env.test`:
```bash
# E2E testing with real APIs
OPENAI_API_KEY=your_openai_api_key_here
RECLAIM_API_KEY=your_reclaim_api_key_here
NYLAS_API_KEY=your_nylas_api_key_here
NYLAS_GRANT_ID=your_nylas_grant_id_here
TEST_USER_TIMEZONE=America/New_York
```

**Why:** E2E tests need ALL credentials including OpenAI (for AI functionality) plus real Reclaim/Nylas keys to test the complete system end-to-end.

## Production Setup

### 1. Create Production Environment

```bash
# Copy the template
cp .env.example .env

# Edit with your actual values
nano .env
```

### 2. Configure Production Environment

```bash
# Required: OpenAI API key for AI functionality
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Server configuration
PORT=5000
HOST=0.0.0.0
FLASK_ENV=production
DEBUG=false

# Security
SECRET_KEY=generate-a-strong-secret-key-here

# Logging
LOG_LEVEL=INFO
```

### 3. Run Production Server

```bash
# Method 1: Using the runner script (recommended)
python scripts/run_server.py

# Method 2: Direct Flask
python -m src.server

# Method 3: With environment variables
OPENAI_API_KEY=your_key FLASK_ENV=production python scripts/run_server.py
```

## Credential Flow Architecture

### Production (Juli → MCP Server)
```
User → Juli App → HTTP Request + Headers → MCP Server
                     ↓
              X-User-Credential-RECLAIM_API_KEY: user_key
              X-User-Credential-NYLAS_API_KEY: user_key
              X-User-Credential-NYLAS_GRANT_ID: user_grant
                     ↓
              MCP Server extracts credentials per-request
                     ↓
              Creates API clients for this user only
```

### Testing (Direct API Access)
```
Test Suite → .env.test credentials → Direct API calls
                     ↓
              Uses your personal API keys
                     ↓
              Tests real API integration
```

## Security Considerations

### Production Security ✅
- ✅ No user credentials stored on server
- ✅ Credentials injected per-request from Juli
- ✅ Each request gets fresh API clients
- ✅ No cross-user data leakage
- ✅ Server only needs OpenAI key for AI features

### Development Security ⚠️
- ⚠️ Test credentials stored in `.env.test`
- ⚠️ Used only for E2E testing
- ⚠️ Never commit real credentials to git
- ⚠️ Use separate test accounts if possible

## Deployment Checklist

### Production Deployment
- [ ] Copy `.env.example` to `.env`
- [ ] Set `OPENAI_API_KEY` in `.env`
- [ ] Set `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=false` and `FLASK_ENV=production`
- [ ] Configure logging level (INFO recommended)
- [ ] Test server startup: `python scripts/run_server.py`
- [ ] Verify health endpoint: `curl http://localhost:5000/health`
- [ ] Configure Juli to send credentials via headers

### E2E Testing Setup  
- [ ] Copy `.env.test.example` to `.env.test`
- [ ] Add your real Reclaim API key to `.env.test`
- [ ] Add your real Nylas API key and grant ID to `.env.test`
- [ ] Set your timezone in `.env.test`
- [ ] Run tests: `pytest tests/e2e -v -m e2e`

## Monitoring & Health Checks

### Health Endpoint
```bash
curl http://localhost:5000/health
# Expected response:
{
  "status": "healthy", 
  "version": "0.1.0"
}
```

### Debug Endpoint (Development Only)
```bash
curl -X POST http://localhost:5000/debug/headers \
  -H "Content-Type: application/json" \
  -H "X-User-Credential-Reclaim-Api-Key: test_key" \
  -d '{}'
```

### Server Logs
The server logs will show:
- ✅ Successful tool executions
- ⚠️ Authentication failures  
- ❌ API errors from Reclaim/Nylas
- 📊 Request/response timing

## Troubleshooting

### "Missing OpenAI API Key"
```bash
# Check if .env exists and has OPENAI_API_KEY
cat .env | grep OPENAI

# Set manually if needed
export OPENAI_API_KEY=your_key_here
python scripts/run_server.py
```

### "No user credentials found"
- Check that Juli is sending headers like `X-User-Credential-RECLAIM_API_KEY`
- Use debug endpoint to verify header format
- Ensure header names match exactly (case-sensitive)

### "Port already in use"
```bash
# Find what's using port 5000
lsof -i :5000

# Kill existing process
pkill -f "python.*server"

# Or use different port
PORT=5001 python scripts/run_server.py
```

The key difference is that production is **stateless** (credentials per-request) while testing uses **stored credentials** for real API testing!