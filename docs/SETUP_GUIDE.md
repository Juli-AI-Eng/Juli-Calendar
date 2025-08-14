# Setup Guide

This guide will walk you through setting up the Juli Calendar Agent for local development and testing.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A Reclaim.ai account
- A Nylas account (for calendar integration)
- An OpenAI API key

## Step 1: Clone the Repository

```bash
git clone https://github.com/Juli-AI/juli-calendar-agent.git
cd juli-calendar-agent
```

## Step 2: Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install the Reclaim SDK (included in the repo)
pip install -e .
```

## Step 3: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Open `.env` in your editor and configure the following:

### OpenAI Configuration

Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys):
```
OPENAI_API_KEY=sk-proj-your-api-key-here
```

### Reclaim.ai Configuration

1. Go to [Reclaim.ai Settings](https://app.reclaim.ai/settings/developer)
2. Click "Generate New API Key"
3. Name it "Juli Integration"
4. Copy the key (this is a long alphanumeric string)
```
RECLAIM_API_KEY=your-reclaim-api-key-here
```

### Nylas Configuration

1. Create an account at [Nylas Dashboard](https://dashboard-v3.nylas.com)
2. Create a new application
3. Copy your credentials:
```
NYLAS_CLIENT_ID=your-client-id
NYLAS_API_KEY=nyk_v0_your-api-key
```

4. Configure the callback URL in Nylas dashboard:
   - For local development: `http://localhost:5002/api/nylas-calendar/callback`
   - For production: `https://your-domain.com/api/nylas-calendar/callback`

5. Set the callback URL in your `.env`:
```
NYLAS_CALLBACK_URI=http://localhost:5002/api/nylas-calendar/callback
```

### A2A Configuration

For local development:
```
A2A_PUBLIC_BASE_URL=http://localhost:5002
A2A_DEV_SECRET=your-dev-secret  # Optional, for development authentication
```

## Step 4: Connect Your Calendar (Nylas OAuth)

1. Start the server:
```bash
python scripts/run_server.py
```

2. Get the OAuth URL:
```bash
curl http://localhost:5002/auth/connect
```

3. Open the returned URL in your browser and complete the OAuth flow

4. After successful authentication, the agent redirects to Juli Brain with the grant_id (following A2A spec). The agent does NOT return JSON or store credentials.

5. Save the grant_id in your `.env` file (optional, for testing):
```
NYLAS_GRANT_ID=your-grant-id-here
```

## Step 5: Verify Your Setup

### Test Server Health
```bash
curl http://localhost:5002/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Test A2A Discovery
```bash
curl http://localhost:5002/.well-known/a2a.json
```

This should return the agent card with capabilities and configuration.

### Test Tool Execution
```bash
curl -X POST http://localhost:5002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "X-A2A-Dev-Secret: your-dev-secret" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tool.execute",
    "params": {
      "tool": "manage_productivity",
      "arguments": {
        "action": "list",
        "query": "Show my tasks for today"
      },
      "user_context": {
        "credentials": {
          "RECLAIM_API_KEY": "your-reclaim-key",
          "NYLAS_GRANT_ID": "your-grant-id"
        },
        "timezone": "America/New_York",
        "current_date": "2024-01-15"
      }
    }
  }'
```

## Step 6: Run Tests

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
# Copy test environment configuration
cp .env.test.example .env.test
# Edit .env.test with your test credentials

# Run integration tests
pytest tests/integration/
```

### E2E Tests
```bash
# Ensure the server is running
python scripts/run_server.py --mode e2e

# In another terminal
pytest tests/e2e/
```

## Troubleshooting

### Port Already in Use
If port 5002 is already in use:
```bash
# Find the process using the port
lsof -i :5002  # On macOS/Linux
netstat -ano | findstr :5002  # On Windows

# Kill the process or change the port in .env
PORT=5003
```

### Nylas OAuth Issues

1. **Invalid credentials**: Ensure your `NYLAS_API_KEY` matches the `NYLAS_CLIENT_ID`
2. **Redirect URI mismatch**: The callback URL in Nylas dashboard must exactly match `NYLAS_CALLBACK_URI`
3. **Wrong region**: Check if you're using the correct API URI (US vs EU)
   - US: `https://api.us.nylas.com`
   - EU: `https://api.eu.nylas.com`

### Reclaim API Issues

1. **Invalid API key**: Ensure your key is a valid Reclaim.ai API key
2. **Rate limiting**: Reclaim has rate limits; implement exponential backoff
3. **Task not appearing**: Reclaim may have a delay in task creation (usually < 30 seconds)

### OpenAI API Issues

1. **Invalid API key**: Ensure your key starts with `sk-proj-`
2. **Rate limiting**: Implement retry logic with exponential backoff
3. **Token limits**: Keep prompts concise; the agent uses GPT-4 by default

## Next Steps

- Read the [Developer Guide](DEVELOPER_GUIDE.md) to understand the architecture
- Check [Tools Documentation](TOOLS_DOCUMENTATION.md) for available tools
- Review [A2A Developer Guide](A2A_DEVELOPER_GUIDE.md) for protocol details
- See [Docker Guide](DOCKER_GUIDE.md) for production deployment

## Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Search [GitHub Issues](https://github.com/Juli-AI/juli-calendar-agent/issues)
3. Create a new issue with detailed error messages and steps to reproduce