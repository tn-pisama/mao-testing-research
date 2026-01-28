# n8n Failure Patterns

Common n8n workflow failure patterns and remediation strategies.

---

## Pattern 1: Infinite Loop in Loop Node

### Description
n8n Loop node continues indefinitely without exit condition.

### Example
```json
{
  "nodes": [
    {
      "type": "n8n-nodes-base.loop",
      "parameters": {
        "maxIterations": 0,  // 0 = infinite
        "exitCondition": "={{false}}"  // Never exits
      }
    }
  ]
}
```

### Detection
- Same node executed 10+ times
- No progress in loop variable
- Duration > expected

### Fix
```json
{
  "parameters": {
    "maxIterations": 100,  // Set reasonable limit
    "exitCondition": "={{$iteration >= 10 || $json.done === true}}"
  }
}
```

---

## Pattern 2: Missing Error Handling

### Description
Node fails but workflow continues, leading to invalid state downstream.

### Example
```json
{
  "nodes": [
    {
      "name": "Fetch Data",
      "type": "n8n-nodes-base.httpRequest",
      "continueOnFail": true,  // Continues even if HTTP fails
      "onError": "continueRegularOutput"
    },
    {
      "name": "Process Data",
      // Assumes data exists, but might be null
    }
  ]
}
```

### Detection
- Node error in execution log
- Workflow status = "success"
- Downstream nodes receive invalid/null data

### Fix
```json
{
  "nodes": [
    {
      "name": "Fetch Data",
      "continueOnFail": false,  // Stop on error
      "onError": "stopWorkflow"
    },
    {
      "name": "Error Handler",
      "type": "n8n-nodes-base.executeWorkflow",
      "parameters": {
        "workflowId": "error-notification-workflow"
      }
    }
  ]
}
```

---

## Pattern 3: Split-Merge Deadlock

### Description
Split node creates multiple branches, but Merge node waits indefinitely for all branches.

### Example
```
Split → [Branch A → (fails)]
     → [Branch B → (completes)]
     → Merge (waits for A forever)
```

### Detection
- Merge node in "waiting" state
- Some branches complete, others don't
- Workflow never finishes

### Fix
```json
{
  "name": "Merge",
  "type": "n8n-nodes-base.merge",
  "parameters": {
    "mode": "waitForCompletion",
    "timeout": 30000,  // 30s timeout
    "onTimeout": "continueWithAvailable"  // Don't wait forever
  }
}
```

---

## Pattern 4: Webhook Timeout

### Description
Webhook receiver times out waiting for n8n workflow to complete.

### Example
```
External Service → n8n Webhook → Long Workflow (2+ minutes) → Response
                                 ↓
                              (timeout)
```

### Detection
- Webhook execution time > 30s
- Caller receives timeout error
- Workflow completes successfully (but response never sent)

### Fix
Use async workflow pattern:
```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "responseMode": "respondImmediately",  // Don't wait for workflow
        "responseData": {
          "status": "processing",
          "tracking_id": "={{$execution.id}}"
        }
      }
    },
    {
      "name": "Long Process",
      // ... workflow continues async
    },
    {
      "name": "Send Callback",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "={{$node.Webhook.json.callback_url}}",
        "method": "POST",
        "body": {
          "tracking_id": "={{$execution.id}}",
          "result": "={{$json}}"
        }
      }
    }
  ]
}
```

---

## Pattern 5: Memory Leak in Function Node

### Description
Function node accumulates data in memory, eventually crashing.

### Example
```javascript
// Function node code
let results = [];  // Global variable persists across items

for (const item of $input.all()) {
  results.push(processItem(item));  // Keeps growing
}

return results;  // All items in memory at once
```

### Detection
- Workflow memory usage increases over time
- Eventually crashes with OOM error
- Performance degrades with more items

### Fix
```javascript
// Process items one at a time, don't accumulate
const processed = $input.all().map(item => processItem(item));
return processed;  // Let n8n handle memory

// Or use streaming mode
return $input.all().map(item => {
  return { json: processItem(item) };
});
```

---

## Pattern 6: Rate Limit Exceeded

### Description
Workflow makes too many API calls, gets rate-limited.

### Example
```
Loop (1000 items) → HTTP Request (no delay) → Rate Limited after 100
```

### Detection
- HTTP 429 errors
- Workflow fails partway through
- Some items processed, others skipped

### Fix
```json
{
  "nodes": [
    {
      "name": "Loop",
      "type": "n8n-nodes-base.loop"
    },
    {
      "name": "Rate Limiter",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 1000,  // Wait 1 second
        "unit": "ms"
      }
    },
    {
      "name": "HTTP Request",
      "parameters": {
        "options": {
          "retry": {
            "maxTries": 3,
            "waitBetween": 5000  // 5s between retries
          }
        }
      }
    }
  ]
}
```

---

## Pattern 7: Missing Data Validation

### Description
Workflow assumes input data structure, but receives unexpected format.

### Example
```javascript
// Function node - assumes data.users exists
return $input.first().json.data.users.map(u => u.email);
// Crashes if data or users is null
```

### Detection
- TypeError: Cannot read property 'users' of null
- Workflow fails unexpectedly
- Works with test data but not production

### Fix
```javascript
// Validate input first
const json = $input.first().json;

if (!json || !json.data || !Array.isArray(json.data.users)) {
  throw new Error('Invalid input: expected data.users array');
}

return json.data.users
  .filter(u => u && u.email)  // Additional safety
  .map(u => u.email);
```

---

## Pattern 8: Credentials Not Found

### Description
Workflow references credentials that don't exist or were deleted.

### Example
```json
{
  "name": "API Call",
  "type": "n8n-nodes-base.httpRequest",
  "credentials": {
    "httpAuth": {
      "id": "deleted-credential-123",
      "name": "API Key (deleted)"
    }
  }
}
```

### Detection
- Error: "Credentials with id X could not be found"
- Workflow worked before, now fails
- Same workflow works for other users

### Fix
1. Check credential still exists: n8n UI → Credentials
2. Re-create credential if deleted
3. Update workflow to use new credential ID

---

## Pattern 9: Environment Variable Not Set

### Description
Workflow uses environment variable that's not configured.

### Example
```javascript
// Function node
const apiKey = $env.API_KEY;  // Undefined in production

fetch('https://api.example.com', {
  headers: { 'Authorization': `Bearer ${apiKey}` }
});
```

### Detection
- Error: "API authentication failed"
- Works locally, fails in production
- apiKey is undefined or null

### Fix
```bash
# Set environment variable in n8n
export API_KEY="your-api-key"

# Or use n8n credentials instead of env vars
```

---

## Pattern 10: Workflow Too Complex

### Description
Single workflow tries to do too much, becomes unmaintainable.

### Example
```
Single workflow with 50+ nodes:
- Data fetch
- Transformation
- Validation
- Business logic
- Error handling
- Notifications
- Logging
```

### Detection
- Workflow execution time > 5 minutes
- Difficult to debug when fails
- Changes break unrelated parts
- Multiple people editing conflicts

### Fix
Split into smaller workflows:
```
Main Workflow:
  → Execute: Data Fetch Workflow
  → Execute: Transform Workflow
  → Execute: Business Logic Workflow
  → Execute: Notification Workflow
```

---

## Remediation Quick Reference

| Failure Pattern | Quick Fix |
|----------------|-----------|
| Infinite loop | Add maxIterations and exit condition |
| Missing error handling | Set continueOnFail=false |
| Split-merge deadlock | Add timeout to merge node |
| Webhook timeout | Use respondImmediately + callback |
| Memory leak | Avoid global variables, process streaming |
| Rate limit | Add delays, implement retry logic |
| Data validation | Validate input before processing |
| Missing credentials | Re-create and link credentials |
| Missing env var | Set environment variable or use credentials |
| Too complex | Split into multiple workflows |
