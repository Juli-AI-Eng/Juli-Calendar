# HTTP MCP Tool Calling Guide

## Overview

This guide shows the complete flow of calling MCP tools via HTTP, from the user's request to the final response, including credential injection.

---

## The Complete Flow

```
User → Juli Frontend → Juli Backend → MCP Server → External Service
                           ↓
                    Inject Credentials
```

1. **User** requests a tool execution (e.g., "Get weather for London")
2. **Juli Frontend** sends request to Juli Backend
3. **Juli Backend** retrieves user's stored credentials
4. **Juli Backend** calls MCP server with credentials in headers
5. **MCP Server** uses credentials to call external service
6. **Response** flows back to user

---

## Step-by-Step Implementation

### 1. User Makes a Request

```javascript
// Juli Frontend - User interface
async function callMCPTool(toolkitId, toolName, args) {
  try {
    const response = await fetch('/api/toolkits/execute', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${userToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        toolkit_id: toolkitId,
        tool_name: toolName,
        arguments: args
      })
    });
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('Tool execution failed:', error);
    throw error;
  }
}

// Example usage
const weather = await callMCPTool(
  'weather-mcp-v1',
  'get_weather',
  { city: 'London', units: 'celsius' }
);
```

### 2. Juli Backend Processes Request

```javascript
// Juli Backend - Main tool execution endpoint
app.post('/api/toolkits/execute', authenticate, async (req, res) => {
  const { toolkit_id, tool_name, arguments } = req.body;
  const userId = req.user.id;
  
  try {
    // 1. Get toolkit configuration
    const toolkit = await getToolkit(toolkit_id);
    
    // 2. Check if user has connected this toolkit
    const credentials = await getUserCredentials(userId, toolkit_id);
    
    if (!credentials) {
      return res.status(400).json({
        error: 'Toolkit not connected',
        action: 'connect_required',
        connect_url: `/connect/${toolkit_id}`
      });
    }
    
    // 3. Call the MCP server
    const result = await callMCPServer(
      toolkit,
      tool_name,
      arguments,
      credentials,
      userId
    );
    
    // 4. Track usage (optional)
    await trackToolUsage(userId, toolkit_id, tool_name);
    
    // 5. Return result
    res.json(result);
    
  } catch (error) {
    handleToolError(error, res);
  }
});
```

### 3. Juli Retrieves and Decrypts Credentials

```javascript
// Get user's credentials for a toolkit
async function getUserCredentials(userId, toolkitId) {
  // Fetch from database
  const record = await db.user_toolkit_credentials.findOne({
    where: { user_id: userId, toolkit_id: toolkitId }
  });
  
  if (!record) return null;
  
  // Check if credentials are still valid
  if (record.status !== 'active') {
    throw new Error('Credentials are invalid or expired');
  }
  
  // Decrypt credentials
  const decrypted = await decryptCredentials(record.encrypted_credentials);
  
  return decrypted;
}

// Decrypt credentials
async function decryptCredentials(encryptedData) {
  const data = JSON.parse(encryptedData);
  const credentials = {};
  
  for (const [key, encryptedValue] of Object.entries(data)) {
    credentials[key] = await decrypt(encryptedValue);
  }
  
  return credentials;
}
```

### 4. Juli Calls MCP Server with Credentials

```javascript
// Call MCP server with credential injection
async function callMCPServer(toolkit, toolName, args, credentials, userId) {
  // Build headers with credentials
  const headers = {
    'Content-Type': 'application/json',
    'X-Platform-User-ID': userId,
    'X-Platform-Request-ID': generateRequestId()
  };
  
  // Inject each credential as a header
  for (const [key, value] of Object.entries(credentials)) {
    headers[`X-User-Credential-${key}`] = value;
  }
  
  // Build the tool execution URL
  const url = toolkit.connection_config.endpoints.execute_tool
    .replace('{toolName}', toolName);
  
  const fullUrl = `${toolkit.connection_config.base_url}${url}`;
  
  // Make the request
  const response = await fetch(fullUrl, {
    method: 'POST',
    headers,
    body: JSON.stringify({ arguments: args })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new MCPError(error, response.status);
  }
  
  return await response.json();
}
```

### 5. MCP Server Receives and Processes Request

```javascript
// MCP Server - Receives request with credentials
app.post('/mcp/tools/:toolName', async (req, res) => {
  const { toolName } = req.params;
  const { arguments } = req.body;
  
  // Extract credentials from headers
  const credentials = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key.startsWith('x-user-credential-')) {
      const credKey = key
        .replace('x-user-credential-', '')
        .toUpperCase()
        .replace(/-/g, '_');
      credentials[credKey] = value;
    }
  }
  
  // Get platform info
  const platformUserId = req.headers['x-platform-user-id'];
  const requestId = req.headers['x-platform-request-id'];
  
  console.log(`Processing ${toolName} for user ${platformUserId} (${requestId})`);
  
  try {
    // Execute the tool with credentials
    let result;
    switch (toolName) {
      case 'get_weather':
        result = await getWeather(arguments, credentials);
        break;
      case 'get_forecast':
        result = await getForecast(arguments, credentials);
        break;
      default:
        return res.status(404).json({ error: `Unknown tool: ${toolName}` });
    }
    
    res.json({ result });
    
  } catch (error) {
    console.error(`Error in ${toolName}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Tool implementation uses the credentials
async function getWeather(args, credentials) {
  const { city, units = 'celsius' } = args;
  const apiKey = credentials.OPENWEATHER_API_KEY;
  
  if (!apiKey) {
    throw new Error('Missing OpenWeatherMap API key');
  }
  
  const response = await fetch(
    `https://api.openweathermap.org/data/2.5/weather?` +
    `q=${encodeURIComponent(city)}&` +
    `appid=${apiKey}&` +
    `units=${units === 'celsius' ? 'metric' : 'imperial'}`
  );
  
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Invalid API key');
    }
    throw new Error(`Weather API error: ${response.statusText}`);
  }
  
  const data = await response.json();
  
  return {
    city: data.name,
    country: data.sys.country,
    temperature: data.main.temp,
    feels_like: data.main.feels_like,
    description: data.weather[0].description,
    humidity: data.main.humidity,
    wind_speed: data.wind.speed,
    units
  };
}
```

---

## Complete Examples

### Example 1: GitHub MCP Tool Call

```javascript
// 1. User wants to list their repos
const repos = await callMCPTool(
  'github-mcp-v1',
  'list_repositories',
  { 
    sort: 'updated',
    per_page: 10 
  }
);

// 2. Juli Backend flow
async function executeGitHubTool(userId, toolName, args) {
  // Get user's GitHub OAuth token
  const credentials = await getUserCredentials(userId, 'github-mcp-v1');
  // credentials = { ACCESS_TOKEN: 'gho_xxxxxxxxxxxx' }
  
  // Call GitHub MCP server
  const response = await fetch('https://github-mcp.example.com/mcp/tools/list_repositories', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Credential-ACCESS_TOKEN': credentials.ACCESS_TOKEN,
      'X-Platform-User-ID': userId
    },
    body: JSON.stringify({ arguments: args })
  });
  
  return response.json();
}

// 3. GitHub MCP Server
async function listRepositories(args, credentials) {
  const { sort, per_page } = args;
  const token = credentials.ACCESS_TOKEN;
  
  const response = await fetch(
    `https://api.github.com/user/repos?sort=${sort}&per_page=${per_page}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json'
      }
    }
  );
  
  const repos = await response.json();
  
  return repos.map(repo => ({
    name: repo.name,
    description: repo.description,
    stars: repo.stargazers_count,
    url: repo.html_url
  }));
}
```

### Example 2: Slack MCP Tool Call

```javascript
// 1. User wants to send a Slack message
const result = await callMCPTool(
  'slack-mcp-v1',
  'send_message',
  {
    channel: 'general',
    text: 'Hello from Juli!'
  }
);

// 2. Juli injects Slack credentials
const response = await fetch('https://slack-mcp.example.com/mcp/tools/send_message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-User-Credential-SLACK_TOKEN': 'xoxb-1234567890-xxxxx',
    'X-User-Credential-WORKSPACE_ID': 'T1234567890',
    'X-Platform-User-ID': 'user_123'
  },
  body: JSON.stringify({
    arguments: {
      channel: 'general',
      text: 'Hello from Juli!'
    }
  })
});

// 3. Slack MCP Server uses credentials
async function sendSlackMessage(args, credentials) {
  const { channel, text } = args;
  const token = credentials.SLACK_TOKEN;
  
  const response = await fetch('https://slack.com/api/chat.postMessage', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      channel: channel,
      text: text
    })
  });
  
  const result = await response.json();
  
  if (!result.ok) {
    throw new Error(result.error || 'Failed to send message');
  }
  
  return {
    success: true,
    channel: result.channel,
    timestamp: result.ts
  };
}
```

### Example 3: Database Query MCP

```javascript
// 1. User wants to query their database
const data = await callMCPTool(
  'postgres-mcp-v1',
  'query',
  {
    sql: 'SELECT * FROM users WHERE created_at > NOW() - INTERVAL \'7 days\''
  }
);

// 2. Juli injects database credentials
const response = await fetch('https://db-mcp.example.com/mcp/tools/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-User-Credential-DB_HOST': 'db.example.com',
    'X-User-Credential-DB_PORT': '5432',
    'X-User-Credential-DB_NAME': 'myapp_production',
    'X-User-Credential-DB_USER': 'myapp_user',
    'X-User-Credential-DB_PASSWORD': 'encrypted_password_here',
    'X-Platform-User-ID': 'user_123'
  },
  body: JSON.stringify({
    arguments: {
      sql: 'SELECT * FROM users WHERE created_at > NOW() - INTERVAL \'7 days\''
    }
  })
});

// 3. Database MCP Server
async function executeQuery(args, credentials) {
  const { sql } = args;
  
  // Create connection with credentials
  const pool = new pg.Pool({
    host: credentials.DB_HOST,
    port: parseInt(credentials.DB_PORT),
    database: credentials.DB_NAME,
    user: credentials.DB_USER,
    password: credentials.DB_PASSWORD
  });
  
  try {
    const result = await pool.query(sql);
    return {
      rows: result.rows,
      rowCount: result.rowCount
    };
  } finally {
    await pool.end();
  }
}
```

---

## Error Handling

### Different Error Types

```javascript
// Juli Backend error handling
function handleToolError(error, res) {
  // Credential errors
  if (error.message.includes('not connected')) {
    return res.status(400).json({
      error: 'Toolkit not connected',
      code: 'TOOLKIT_NOT_CONNECTED',
      action: {
        type: 'connect',
        message: 'Please connect this toolkit first'
      }
    });
  }
  
  // MCP server errors
  if (error instanceof MCPError) {
    if (error.status === 401) {
      return res.status(401).json({
        error: 'Invalid credentials',
        code: 'INVALID_CREDENTIALS',
        action: {
          type: 'reconnect',
          message: 'Your credentials may have expired. Please reconnect.'
        }
      });
    }
    
    if (error.status === 429) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        code: 'RATE_LIMIT',
        retry_after: error.retryAfter
      });
    }
  }
  
  // Generic error
  console.error('Tool execution error:', error);
  res.status(500).json({
    error: 'Tool execution failed',
    message: error.message
  });
}
```

### User-Friendly Error Messages

```javascript
// Frontend error handling
async function handleToolError(error) {
  switch (error.code) {
    case 'TOOLKIT_NOT_CONNECTED':
      showModal({
        title: 'Connect Required',
        message: 'You need to connect this toolkit before using it.',
        actions: [
          { label: 'Connect Now', action: () => connectToolkit(toolkitId) },
          { label: 'Cancel', action: () => closeModal() }
        ]
      });
      break;
      
    case 'INVALID_CREDENTIALS':
      showModal({
        title: 'Authentication Failed',
        message: 'Your credentials may have expired or been revoked.',
        actions: [
          { label: 'Reconnect', action: () => reconnectToolkit(toolkitId) },
          { label: 'Cancel', action: () => closeModal() }
        ]
      });
      break;
      
    case 'RATE_LIMIT':
      showToast({
        type: 'warning',
        message: `Rate limit exceeded. Try again in ${error.retry_after} seconds.`
      });
      break;
      
    default:
      showToast({
        type: 'error',
        message: error.message || 'Something went wrong'
      });
  }
}
```

---

## Rate Limiting and Usage Tracking

### Juli Backend Tracking

```javascript
// Track tool usage for analytics and billing
async function trackToolUsage(userId, toolkitId, toolName) {
  await db.tool_usage.create({
    user_id: userId,
    toolkit_id: toolkitId,
    tool_name: toolName,
    executed_at: new Date()
  });
  
  // Check user limits
  const usage = await getUserUsageStats(userId, toolkitId);
  
  if (usage.monthly_calls > usage.plan_limit) {
    throw new Error('Monthly usage limit exceeded');
  }
}

// Get usage statistics
async function getUserUsageStats(userId, toolkitId) {
  const startOfMonth = new Date();
  startOfMonth.setDate(1);
  startOfMonth.setHours(0, 0, 0, 0);
  
  const count = await db.tool_usage.count({
    where: {
      user_id: userId,
      toolkit_id: toolkitId,
      executed_at: { [Op.gte]: startOfMonth }
    }
  });
  
  return {
    monthly_calls: count,
    plan_limit: 1000 // Example limit
  };
}
```

---

## Caching Results (Optional)

```javascript
// Cache frequently accessed data
const cache = new Map();

async function callMCPServerWithCache(toolkit, toolName, args, credentials, userId) {
  // Generate cache key
  const cacheKey = `${toolkit.id}:${toolName}:${JSON.stringify(args)}:${userId}`;
  
  // Check cache
  if (cache.has(cacheKey)) {
    const cached = cache.get(cacheKey);
    if (Date.now() - cached.timestamp < 300000) { // 5 minutes
      console.log('Returning cached result');
      return cached.data;
    }
  }
  
  // Call MCP server
  const result = await callMCPServer(toolkit, toolName, args, credentials, userId);
  
  // Cache result
  cache.set(cacheKey, {
    data: result,
    timestamp: Date.now()
  });
  
  return result;
}
```

---

## Testing Tool Calls

### Test Script

```javascript
// test-tool-execution.js
async function testToolExecution() {
  const API_URL = 'http://localhost:3000/api';
  const USER_TOKEN = 'test_user_token';
  
  // Test 1: Call weather tool
  console.log('Testing weather tool...');
  
  const weatherResult = await fetch(`${API_URL}/toolkits/execute`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${USER_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      toolkit_id: 'weather-mcp-v1',
      tool_name: 'get_weather',
      arguments: {
        city: 'London',
        units: 'celsius'
      }
    })
  });
  
  console.log('Weather result:', await weatherResult.json());
  
  // Test 2: Handle not connected error
  console.log('\nTesting not connected error...');
  
  const errorResult = await fetch(`${API_URL}/toolkits/execute`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${USER_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      toolkit_id: 'github-mcp-v1',
      tool_name: 'list_repos',
      arguments: {}
    })
  });
  
  console.log('Error result:', await errorResult.json());
}

testToolExecution();
```

---

## Summary

The complete flow for calling MCP tools:

1. **User** makes request through Juli UI
2. **Juli Frontend** sends to backend API
3. **Juli Backend**:
   - Validates user has connected the toolkit
   - Retrieves and decrypts stored credentials
   - Injects credentials as HTTP headers
   - Calls MCP server
4. **MCP Server**:
   - Extracts credentials from headers
   - Uses credentials to call external service
   - Returns results
5. **Response** flows back to user

Key points:
- Credentials are injected as `X-User-Credential-*` headers
- Each tool call is independent (stateless)
- Proper error handling for credential issues
- Usage tracking for analytics/billing
- Optional caching for performance