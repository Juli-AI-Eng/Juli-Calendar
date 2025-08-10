# Juli Approval System Guide

Understanding how the approval system works between Juli and MCP servers for safe execution of sensitive actions.

## Overview

The approval system ensures users maintain control over potentially impactful actions. When an MCP server needs user confirmation before proceeding, it returns a special response that Juli intercepts and handles with a native UI.

## How It Works

### Flow Diagram

```
User Request → MCP Server → Needs Approval? → Return Approval Request
                                ↓                        ↓
                              No                    Juli Shows UI
                                ↓                        ↓
                          Execute Action            User Decides
                                                         ↓
                                                   Approve/Deny
                                                         ↓
                                                  Retry with Decision
```

### The Stateless Approval Protocol

**Key Principle**: MCP servers don't store pending approvals. Instead, they return all data needed to execute the action, and Juli handles the approval UI and retry.

## Implementation

### 1. When to Require Approval

```typescript
function needsApproval(action: any): boolean {
  // Require approval for:
  // - Sending emails
  // - Deleting data
  // - Bulk operations
  // - Financial transactions
  // - Any irreversible actions
  
  return action.type === 'send' || 
         action.bulk_count > 10 ||
         action.involves_money ||
         action.is_destructive;
}
```

### 2. Approval Response Format

```typescript
interface ApprovalRequiredResponse {
  needs_approval: true;
  action_type: string;        // Type of action requiring approval
  action_data: any;          // Complete data needed to execute
  preview: {
    summary: string;         // One-line summary
    details: any;           // Detailed preview info
    risks?: string[];       // Optional warnings
  };
  suggested_modifications?: any;  // Optional suggestions
}
```

### 3. Real Example: Email Approval

```typescript
// User says: "reply to Sarah about the meeting"
async function handleManageEmail(params: any) {
  // AI generates the email
  const emailContent = await generateEmail(params.query);
  
  // Check if approval needed
  if (params.action === 'send' && !params.approved) {
    return {
      needs_approval: true,
      action_type: 'send_email',
      action_data: {
        email_content: {
          to: ['sarah@company.com'],
          subject: 'Re: Tomorrow\'s Meeting',
          body: 'Hi Sarah,\n\nThank you for...',
          thread_id: 'thread_123'
        },
        original_params: params
      },
      preview: {
        summary: 'Send email to sarah@company.com',
        details: {
          recipient: 'Sarah Johnson',
          subject: 'Re: Tomorrow\'s Meeting',
          word_count: 127,
          has_attachments: false
        }
      }
    };
  }
  
  // If approved, execute
  if (params.approved && params.action_data) {
    const result = await sendEmail(params.action_data.email_content);
    return {
      success: true,
      message: 'Email sent successfully',
      message_id: result.id
    };
  }
}
```

### 4. Bulk Operations Example

```typescript
// User says: "archive all newsletters older than a month"
async function handleOrganizeInbox(params: any) {
  // Find matching emails
  const emails = await findEmails({
    category: 'newsletter',
    older_than: '1 month'
  });
  
  // Require approval for bulk operations
  if (!params.confirmed) {
    return {
      needs_approval: true,
      action_type: 'bulk_archive',
      action_data: {
        email_ids: emails.map(e => e.id),
        operation: 'archive',
        filter_used: params.instruction
      },
      preview: {
        summary: `Archive ${emails.length} newsletters`,
        details: {
          count: emails.length,
          oldest_email: emails[0]?.date,
          newest_email: emails[emails.length-1]?.date,
          sample_subjects: emails.slice(0, 3).map(e => e.subject)
        },
        risks: emails.length > 100 ? 
          ['This will archive a large number of emails'] : 
          undefined
      }
    };
  }
  
  // Execute if confirmed
  if (params.confirmed && params.action_data) {
    await archiveEmails(params.action_data.email_ids);
    return {
      success: true,
      message: `Archived ${params.action_data.email_ids.length} emails`
    };
  }
}
```

## What Juli Handles

### 1. Approval UI

When Juli receives a `needs_approval` response, it:

```typescript
// Juli's internal handling
if (response.needs_approval) {
  // Show native approval dialog
  const userDecision = await showApprovalDialog({
    title: response.action_type,
    summary: response.preview.summary,
    details: response.preview.details,
    risks: response.preview.risks
  });
  
  if (userDecision.approved) {
    // Retry with approval
    const finalResponse = await callMCPTool(toolName, {
      ...originalParams,
      approved: true,
      action_data: response.action_data
    });
    return finalResponse;
  } else {
    // User denied
    return {
      cancelled: true,
      message: 'Action cancelled by user'
    };
  }
}
```

### 2. Approval UI Components

Juli renders a beautiful approval dialog with:
- Clear action summary
- Detailed preview (formatted based on action type)
- Risk warnings in red
- Approve/Deny buttons
- Optional "Modify" button for editable actions

### 3. Modification Flow

For editable actions (like emails), users can modify before approving:

```typescript
// MCP returns suggested modifications
{
  needs_approval: true,
  action_type: 'send_email',
  action_data: { ... },
  preview: { ... },
  suggested_modifications: {
    editable_fields: ['body', 'subject'],
    constraints: {
      body: { max_length: 10000 },
      subject: { max_length: 200 }
    }
  }
}

// Juli allows editing these fields in the approval dialog
```

## Best Practices

### 1. Clear Preview Information

```typescript
// ✅ Good: Specific and actionable
preview: {
  summary: 'Send email to 3 team members about project update',
  details: {
    recipients: ['john@company.com', 'sarah@company.com', 'mike@company.com'],
    subject: 'Project Alpha: Status Update',
    mentions_deadline: true,
    attachments: 0
  }
}

// ❌ Bad: Vague
preview: {
  summary: 'Send email',
  details: { count: 3 }
}
```

### 2. Appropriate Risk Warnings

```typescript
risks: [
  // Only include real risks
  'This will permanently delete 42 records',
  'Email will be sent to all 1,847 subscribers',
  'This action cannot be undone'
]

// Don't include non-risks like:
// 'This will send an email' (obvious from action)
// 'Please review before approving' (redundant)
```

### 3. Granular Approval Control

```typescript
// Allow users to control approval preferences
interface ToolParams {
  require_approval?: boolean;  // Override default
  auto_approve_threshold?: number;  // For bulk operations
}

// Example: Don't require approval for small operations
if (emails.length <= 5 && !params.require_approval) {
  // Execute without approval
}
```

### 4. Stateless Design

```typescript
// ✅ Good: Return all data needed
return {
  needs_approval: true,
  action_data: {
    email_content: fullEmailObject,
    thread_id: threadId,
    references: messageReferences
  }
};

// ❌ Bad: Storing state
const approvalId = generateId();
pendingApprovals.set(approvalId, emailData);
return {
  needs_approval: true,
  approval_id: approvalId  // Don't do this!
};
```

## Common Approval Scenarios

### 1. Communication Actions
- Sending emails
- Posting to social media
- Sending messages
- Making phone calls

### 2. Data Modifications
- Deleting records
- Bulk updates
- Archiving content
- Modifying sensitive data

### 3. Financial Operations
- Processing payments
- Issuing refunds
- Changing billing
- Subscription modifications

### 4. System Changes
- Deploying code
- Changing configurations
- Updating permissions
- Modifying integrations

## Testing Approvals

```typescript
describe('Approval Flow', () => {
  it('should require approval for sending emails', async () => {
    const response = await mcp.handleTool('manage_email', {
      action: 'send',
      query: 'email John about the meeting'
    });
    
    expect(response.needs_approval).toBe(true);
    expect(response.action_type).toBe('send_email');
    expect(response.action_data).toHaveProperty('email_content');
    expect(response.preview.summary).toContain('Send email');
  });
  
  it('should execute when approved', async () => {
    const approvalResponse = await mcp.handleTool('manage_email', {
      action: 'send',
      query: 'email John about the meeting'
    });
    
    const finalResponse = await mcp.handleTool('manage_email', {
      ...approvalResponse.action_data.original_params,
      approved: true,
      action_data: approvalResponse.action_data
    });
    
    expect(finalResponse.success).toBe(true);
    expect(finalResponse.message).toContain('sent');
  });
});
```

## Security Considerations

### 1. Action Data Validation

Always re-validate action data when executing approved actions:

```typescript
if (params.approved && params.action_data) {
  // Re-validate the action data
  if (!isValidEmailContent(params.action_data.email_content)) {
    return {
      error: 'Invalid email content in approval data'
    };
  }
  
  // Verify it matches what would be generated
  const expectedContent = await generateEmail(params.action_data.original_params);
  if (!contentMatches(expectedContent, params.action_data.email_content)) {
    return {
      error: 'Approval data does not match expected content'
    };
  }
}
```

### 2. Prevent Approval Bypass

```typescript
// Always check approval status for sensitive actions
if (action.type === 'send' && !params.approved) {
  // Force approval flow
  return { needs_approval: true, ... };
}

// Don't allow approval flag without action_data
if (params.approved && !params.action_data) {
  return {
    error: 'Approved flag requires action_data'
  };
}
```

## Summary

The Juli approval system provides:

1. **User Control** - Users always have final say on sensitive actions
2. **Transparency** - Clear previews of what will happen
3. **Flexibility** - Developers decide what needs approval
4. **Simplicity** - Stateless design makes implementation easy
5. **Security** - No way to bypass user approval for sensitive actions

By following this guide, your MCP server will integrate seamlessly with Juli's approval system, giving users confidence to use powerful tools while maintaining control over their data and actions.