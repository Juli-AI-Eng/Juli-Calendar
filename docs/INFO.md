# Juli Developer Integration Guide

Welcome to Juli! This guide will help you create powerful, AI-optimized toolkits that work seamlessly with our platform. Follow these principles to ensure your users have the best experience possible.

## Table of Contents
1. [The Golden Rule: Think Like an AI](#the-golden-rule-think-like-an-ai)
2. [Core Principles](#core-principles)
3. [Tool Design Best Practices](#tool-design-best-practices)
4. [Context Injection](#context-injection)
5. [MCP Server vs REST API](#mcp-server-vs-rest-api)
6. [Examples](#examples)
7. [Common Mistakes to Avoid](#common-mistakes-to-avoid)
8. [Testing and Validation](#testing-and-validation)

## The Golden Rule: Think Like an AI

> "Put yourself in the shoes of the AI when designing your toolkit. Ask yourself: Based on these descriptions alone, would I know when and how to use each tool?"

This is Juli's most important principle. Every decision you make should be filtered through this lens. The AI doesn't have context about your business logic - it only has your descriptions and parameter schemas to work with.

## Core Principles

### 1. Limit Your Toolkit to 5 Tools or Fewer

This isn't just a suggestion - it's backed by data:

- **With 5 or fewer tools**: ~95% accuracy in tool selection
- **With 10 tools**: ~80% accuracy
- **With 20+ tools**: accuracy drops below 60%

When you exceed 5 tools, you'll see a warning in the Juli interface. This is because AI models like Claude and OpenAI perform significantly better with a focused set of tools.

### 2. Consolidate Similar Tools (But Be Smart About It)

Don't create separate tools for minor variations. Instead, use parameters to handle different use cases. However, don't go overboard with full CRUD consolidation - find the middle ground.

**❌ Bad: Too Many Specific Tools**
```json
{
  "tools": [
    { "name": "get_user_by_id" },
    { "name": "get_user_by_email" },
    { "name": "get_user_by_username" },
    { "name": "update_user_email" },
    { "name": "update_user_name" },
    { "name": "update_user_phone" },
    { "name": "delete_user_by_id" },
    { "name": "delete_user_by_email" }
  ]
}
```

**✅ Good: Smart Consolidation**
```json
{
  "tools": [
    { 
      "name": "get_users",
      "description": "Retrieve user information by various identifiers",
      "parameters": {
        "properties": {
          "identifier_type": {
            "enum": ["id", "email", "username"],
            "description": "Type of identifier to search by"
          },
          "identifier_value": {
            "type": "string",
            "description": "The actual identifier value"
          }
        }
      }
    },
    { 
      "name": "update_user",
      "description": "Update specific user fields",
      "parameters": {
        "properties": {
          "user_id": { "type": "string" },
          "updates": {
            "type": "object",
            "description": "Fields to update",
            "properties": {
              "email": { "type": "string" },
              "name": { "type": "string" },
              "phone": { "type": "string" }
            }
          }
        }
      }
    },
    { 
      "name": "delete_user",
      "parameters": {
        "properties": {
          "user_id": { "type": "string" }
        }
      }
    }
  ]
}
```

### 3. Write Crystal Clear Descriptions

Remember: **Less hallucinations = happy customers!**

Every level needs clear descriptions:

- **Toolkit Description**: What your entire toolkit does
- **Tool Descriptions**: Specific purpose and when to use it
- **Parameter Descriptions**: What each parameter controls

Your descriptions should answer:
- What does this do?
- When should it be used?
- What data does it return?

## Tool Design Best Practices

### 1. Use Action-Oriented Names

- ✅ `analyze_code`
- ✅ `create_report`
- ✅ `search_products`
- ❌ `code`
- ❌ `report`
- ❌ `products`

### 2. Design Flexible Parameters

Make parameters optional when possible and provide sensible defaults:

```json
{
  "name": "analyze_code",
  "parameters": {
    "properties": {
      "code": {
        "type": "string",
        "description": "Source code to analyze",
        "minLength": 1,
        "maxLength": 50000
      },
      "language": {
        "type": "string",
        "description": "Programming language",
        "enum": ["javascript", "python", "java", "typescript", "go", "rust"]
      },
      "analysis_types": {
        "type": "array",
        "description": "Types of analysis to perform",
        "items": {
          "enum": ["bugs", "performance", "security", "style", "complexity"]
        },
        "default": ["bugs", "performance"]
      }
    },
    "required": ["code", "language"]
  }
}
```

### 3. Use Enums for Controlled Options

When you have a fixed set of options, use enums to prevent the AI from hallucinating invalid values:

```json
{
  "output_format": {
    "type": "string",
    "description": "Desired output format",
    "enum": ["json", "csv", "pdf", "excel"],
    "default": "json"
  }
}
```

## Context Injection

One of Juli's most powerful features is **Context Injection** - it automatically fills parameters with real user data to prevent AI hallucinations.

### Why It Matters

When AI models don't have access to user-specific information (like user ID, location, or timezone), they may:
- Make up values
- Ask unnecessary questions
- Provide generic responses

### How to Use It

For any parameter that should come from user context, enable "Auto-fill from user context" in the parameter configuration. Available context fields include:

- `user_id`
- `user_name`
- `user_email`
- `user_location`
- `user_timezone`
- `user_time`

**Example:**
```json
{
  "name": "get_personalized_recommendations",
  "parameters": {
    "properties": {
      "user_id": {
        "type": "string",
        "description": "User's unique identifier",
        "x-context-injection": "user_id"  // This tells Juli to auto-fill
      },
      "timezone": {
        "type": "string",
        "description": "User's timezone for time-sensitive recommendations",
        "x-context-injection": "user_timezone"
      }
    }
  }
}
```

## MCP Server vs REST API

### MCP Server Example

MCP servers are ideal for complex, stateful operations:

```json
{
  "toolkit_type": "mcp_server",
  "name": "ai_assistant_mcp",
  "description": "MCP server providing AI-powered assistance and analysis tools",
  "version": "1.0.0",
  "tools": [
    {
      "name": "analyze_code",
      "description": "Analyze code for bugs, performance issues, and best practices",
      "inputSchema": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "description": "Source code to analyze",
            "minLength": 1,
            "maxLength": 50000
          },
          "language": {
            "type": "string",
            "enum": ["javascript", "python", "java", "typescript", "go", "rust"]
          },
          "analysis_types": {
            "type": "array",
            "items": {
              "enum": ["bugs", "performance", "security", "style", "complexity"]
            },
            "minItems": 1
          }
        },
        "required": ["code", "language", "analysis_types"]
      }
    }
  ],
  "connection_config": {
    "transport": "websocket",
    "connection_uri": "wss://mcp.example.com/connect"
  }
}
```

### REST API Example

REST APIs are perfect for straightforward request-response operations:

```json
{
  "toolkit_type": "rest_api",
  "name": "analytics_toolkit",
  "description": "Analytics toolkit for generating and managing reports",
  "version": "1.0.0",
  "base_url": "https://api.analytics.example.com",
  "tools": [
    {
      "name": "create_report",
      "description": "Generate analytics report with multiple configuration options",
      "endpoint": "/reports",
      "method": "POST",
      "parameters": {
        "type": "object",
        "properties": {
          "report_name": {
            "type": "string",
            "description": "Name of the report",
            "minLength": 3,
            "maxLength": 100
          },
          "date_range": {
            "type": "object",
            "properties": {
              "start_date": { "type": "string", "format": "date" },
              "end_date": { "type": "string", "format": "date" }
            },
            "required": ["start_date", "end_date"]
          },
          "metrics": {
            "type": "array",
            "items": {
              "enum": ["views", "clicks", "conversions", "revenue"]
            },
            "minItems": 1,
            "maxItems": 5
          }
        },
        "required": ["report_name", "date_range", "metrics"]
      }
    },
    {
      "name": "get_report_status",
      "description": "Check the status of a report generation job",
      "endpoint": "/reports/{report_id}/status",
      "method": "GET",
      "parameters": {
        "properties": {
          "report_id": {
            "type": "string",
            "pattern": "^[a-f0-9-]{36}$"
          }
        },
        "required": ["report_id"]
      }
    }
  ]
}
```

## Examples

### Example 1: E-commerce Toolkit (Good Design)

```json
{
  "name": "shopify_toolkit",
  "description": "Manage products and orders in Shopify stores",
  "tools": [
    {
      "name": "manage_products",
      "description": "Search, create, update, or delete products",
      "parameters": {
        "properties": {
          "action": {
            "enum": ["search", "create", "update", "delete"],
            "description": "Action to perform"
          },
          "filters": {
            "description": "Search filters (for search action)",
            "properties": {
              "query": { "type": "string" },
              "category": { "type": "string" },
              "price_range": {
                "properties": {
                  "min": { "type": "number" },
                  "max": { "type": "number" }
                }
              }
            }
          },
          "product_data": {
            "description": "Product information (for create/update)"
          },
          "product_id": {
            "description": "Product ID (for update/delete)"
          }
        }
      }
    },
    {
      "name": "manage_orders",
      "description": "View and update order information",
      "parameters": {
        "properties": {
          "action": {
            "enum": ["list", "get_details", "update_status"],
            "description": "Action to perform"
          },
          "order_id": { "type": "string" },
          "status": {
            "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]
          },
          "date_range": {
            "properties": {
              "start": { "type": "string", "format": "date" },
              "end": { "type": "string", "format": "date" }
            }
          }
        }
      }
    },
    {
      "name": "generate_analytics",
      "description": "Generate sales and inventory analytics reports"
    }
  ]
}
```

### Example 2: Customer Support Toolkit (With Context Injection)

```json
{
  "name": "support_toolkit",
  "description": "Customer support tools for ticket and knowledge base management",
  "tools": [
    {
      "name": "manage_tickets",
      "description": "Create, view, or update support tickets",
      "parameters": {
        "properties": {
          "action": {
            "enum": ["create", "view", "update", "list_my_tickets"]
          },
          "customer_id": {
            "description": "Customer ID (auto-filled from context)",
            "x-context-injection": "user_id"
          },
          "ticket_data": {
            "properties": {
              "subject": { "type": "string" },
              "description": { "type": "string" },
              "priority": { "enum": ["low", "medium", "high", "urgent"] }
            }
          }
        }
      }
    },
    {
      "name": "search_knowledge_base",
      "description": "Search help articles and documentation"
    },
    {
      "name": "check_service_status",
      "description": "Get current system status and known issues"
    }
  ]
}
```

## Common Mistakes to Avoid

### 1. Tool Sprawl
**Problem**: Creating a separate tool for every minor variation
**Solution**: Use parameters to handle variations

### 2. Vague Descriptions
**Problem**: "Handles user requests" or "Processes data"
**Solution**: Be specific about what the tool does and when to use it

### 3. Overlapping Functions
**Problem**: Multiple tools that do similar things
**Solution**: Consolidate into one tool with clear parameters

### 4. Missing Context
**Problem**: Requiring user-specific data without context injection
**Solution**: Use context injection for user-specific parameters

### 5. Over-Consolidation
**Problem**: One mega-tool that does everything
**Solution**: Find the middle ground - consolidate similar functions, keep distinct operations separate

## Testing and Validation

Before submitting your toolkit:

1. **Test Each Tool**: Verify all tools work with various inputs
2. **Check Error Handling**: Ensure graceful handling of invalid inputs
3. **Validate Descriptions**: Read them as if you knew nothing about your system
4. **Test Authentication**: Verify your auth configuration works correctly
5. **Review Consolidation**: Could any tools be combined? Are any too complex?

### The AI Test

For each tool, ask yourself:
- Would an AI know when to use this tool based solely on its name and description?
- Are the parameters clear enough that an AI won't hallucinate values?
- Does the tool overlap with others in confusing ways?

## Summary

Remember Juli's philosophy:
- **Less tools = better AI performance**
- **Clear descriptions = fewer hallucinations**
- **Smart consolidation = happy users**
- **Think like an AI = successful integration**

When in doubt, always go back to the golden rule: **Think Like an AI**. If you wouldn't know how to use your toolkit based on the descriptions alone, neither will the AI.

Thank you for building with Juli! 🚀