# API Contract - KaryaKarta Agent System

**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Status**: Active

## Overview

This document defines the contract between the Next.js frontend and Python backend.
**Both teams MUST adhere to this contract.**

Any changes to this contract require approval from both frontend and backend teams.

---

## REST API Endpoints

### POST /execute-task

Execute an agent task with message tracking.

**Endpoint**: `POST http://localhost:8000/execute-task`

**Request Body**:
```typescript
interface TaskRequest {
  prompt: string;           // User's message/query
  messageId: string;        // Unique message ID (format: msg_{timestamp}_{random})
  sessionId?: string;       // Optional session ID (default: "default")
}
```

**Response**:
```typescript
interface TaskResponse {
  status: "success" | "error" | "already_processing" | "already_completed";
  messageId: string;        // Echo back the message ID
  sessionId: string;        // Session ID used
  error?: string;           // Error message if status is "error"
}
```

**Example Request**:
```bash
curl -X POST http://localhost:8000/execute-task \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Find Mexican restaurants near Mill Creek WA",
    "messageId": "msg_1729876543210_abc123",
    "sessionId": "session_user123"
  }'
```

**Example Response**:
```json
{
  "status": "success",
  "messageId": "msg_1729876543210_abc123",
  "sessionId": "session_user123"
}
```

**Status Codes**:
- `200 OK`: Request accepted
- `400 Bad Request`: Invalid request format
- `500 Internal Server Error`: Server error

---

## WebSocket Protocol

### Connection

- **Protocol**: Socket.IO
- **Frontend URL**: `http://localhost:3000`
- **Backend connects to**: `http://localhost:3000/api/socket/log`
- **Event Name**: `agent-log`

### Message Types

All messages sent via WebSocket follow this base structure:

```typescript
interface BaseMessage {
  type: "status" | "thinking" | "response" | "error";
  message: string;
  timestamp: string;        // ISO 8601 format
  messageId?: string;       // Links to original request (optional for status/thinking)
}
```

#### 1. Status Message

Updates about agent's current operation (e.g., "Searching...", "Processing...")

```typescript
interface StatusMessage extends BaseMessage {
  type: "status";
  message: string;
  timestamp: string;
  messageId?: string;
}
```

**Example**:
```json
{
  "type": "status",
  "message": "Searching Google for: Mexican restaurants Mill Creek WA",
  "timestamp": "2025-10-25T12:00:00.000Z",
  "messageId": "msg_1729876543210_abc123"
}
```

#### 2. Thinking Message

Agent's reasoning process (e.g., "Analyzing results...", "Planning next step...")

```typescript
interface ThinkingMessage extends BaseMessage {
  type: "thinking";
  message: string;
  timestamp: string;
  messageId?: string;
}
```

**Example**:
```json
{
  "type": "thinking",
  "message": "Agent is analyzing search results and planning next steps...",
  "timestamp": "2025-10-25T12:00:01.000Z",
  "messageId": "msg_1729876543210_abc123"
}
```

#### 3. Response Message

**Final answer to user's query. This is the agent's complete response.**

```typescript
interface ResponseMessage extends BaseMessage {
  type: "response";
  message: string;
  timestamp: string;
  messageId: string;        // REQUIRED for deduplication
}
```

**Example**:
```json
{
  "type": "response",
  "message": "I found 5 Mexican restaurants near Mill Creek WA:\n\n1. Casa Durango - Walk-ins accepted\n2. Azteca - Reservations available via OpenTable...",
  "timestamp": "2025-10-25T12:00:05.000Z",
  "messageId": "msg_1729876543210_abc123"
}
```

#### 4. Error Message

Errors during processing.

```typescript
interface ErrorMessage extends BaseMessage {
  type: "error";
  message: string;
  timestamp: string;
  messageId?: string;
  errorCode?: string;
}
```

**Example**:
```json
{
  "type": "error",
  "message": "Failed to search: API rate limit exceeded",
  "timestamp": "2025-10-25T12:00:02.000Z",
  "messageId": "msg_1729876543210_abc123",
  "errorCode": "RATE_LIMIT_EXCEEDED"
}
```

---

## Data Models

### Message ID Format

**Format**: `msg_{timestamp}_{random}`

**Example**: `msg_1729876543210_abc123`

**Generation Rules**:
- `timestamp`: Current time in milliseconds (13 digits)
- `random`: Random alphanumeric string (7-8 characters)
- Total length: ~30 characters

**Frontend Implementation (TypeScript)**:
```typescript
export const generateMessageId = (): string => {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 9);
  return `msg_${timestamp}_${random}`;
};
```

**Backend Implementation (Python)**:
```python
import uuid
from datetime import datetime

def generate_message_id() -> str:
    """Generate a unique message ID."""
    timestamp = int(datetime.now().timestamp() * 1000)
    unique_id = str(uuid.uuid4())[:8]
    return f"msg_{timestamp}_{unique_id}"
```

### Session ID Format

**Format**: `session_{identifier}_{timestamp}`

**Example**: `session_user123_1729876543210`

**Rules**:
- Frontend generates and maintains session IDs
- Session IDs should persist across page refreshes (use localStorage)
- New session = new conversation context

---

## Frontend Requirements

### 1. Message ID Generation

The frontend **MUST**:
- Generate unique message IDs for each user message
- Include messageId in all `/execute-task` requests
- Track processed message IDs to prevent duplicate rendering

```typescript
// Generate ID when user sends message
const messageId = generateMessageId();

// Send to backend
await fetch('/api/agent/run', {
  method: 'POST',
  body: JSON.stringify({ prompt, messageId, sessionId })
});
```

### 2. Deduplication Logic

The frontend **MUST** implement deduplication:

```typescript
const processedMessageIds = useRef<Set<string>>(new Set());

socket.on('agent-log', (data: AgentMessage) => {
  // Only deduplicate response messages
  if (data.type === 'response' && data.messageId) {
    if (processedMessageIds.current.has(data.messageId)) {
      console.log('Duplicate response detected, skipping');
      return;
    }
    processedMessageIds.current.add(data.messageId);
  }
  
  // Process message...
});
```

### 3. Session Management

The frontend **SHOULD**:
- Maintain sessionId across the conversation
- Store in React state or localStorage
- Generate new sessionId for new conversations

```typescript
const [sessionId, setSessionId] = useState(() => {
  // Try to restore from localStorage
  return localStorage.getItem('sessionId') || generateSessionId();
});

useEffect(() => {
  localStorage.setItem('sessionId', sessionId);
}, [sessionId]);
```

### 4. Message Display

The frontend **MUST**:
- Display status/thinking messages in real-time
- Show final response message prominently
- Handle errors gracefully
- Link responses to original user messages via messageId

---

## Backend Requirements

### 1. Message Tracking

The backend **MUST**:
- Track all processed message IDs
- Prevent duplicate processing of same messageId
- Return appropriate status for duplicates

```python
# Global tracking
processed_messages: Set[str] = set()
active_messages: Dict[str, MessageMetadata] = {}

@app.post("/execute-task")
async def execute_task(request: TaskRequest):
    # Check for duplicates
    if request.messageId in processed_messages:
        return TaskResponse(
            status="already_completed",
            messageId=request.messageId,
            sessionId=request.sessionId
        )
    
    if request.messageId in active_messages:
        return TaskResponse(
            status="already_processing",
            messageId=request.messageId,
            sessionId=request.sessionId
        )
```

### 2. Include Message ID in Logs

The backend **MUST**:
- Include messageId in ALL WebSocket messages (especially responses)
- This enables frontend to link responses to requests

```python
def send_log_to_socket(
    message: str, 
    message_type: str = "status",
    message_id: Optional[str] = None
):
    payload = {
        'type': message_type,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'messageId': message_id  # Include this!
    }
    requests.post(LOGGING_URL, json=payload)
```

### 3. Session Persistence

The backend **MUST**:
- Maintain conversation history per sessionId
- Use LangGraph checkpointing for memory
- Clean up old sessions periodically

```python
# Use session-based memory
result = agent.invoke(
    {"messages": [HumanMessage(content=prompt)]},
    config={"configurable": {"thread_id": session_id}}
)
```

---

## Message Flow Diagram

```
Frontend                    Backend                     User
   |                          |                          |
   |-- 1. User types msg ----->|                          |
   |                          |                          |
   |<- 2. Generate msg ID -----|                          |
   |   (msg_123_abc)          |                          |
   |                          |                          |
   |-- 3. POST /execute-task ->|                          |
   |   {prompt, messageId}    |                          |
   |                          |                          |
   |<- 4. 200 OK --------------|                          |
   |   {status: "success"}    |                          |
   |                          |                          |
   |                          |-- 5. Process task ------->|
   |                          |                          |
   |<- 6. WS: status msg ------|                          |
   |   {type: "status"}       |                          |
   |                          |                          |
   |<- 7. WS: thinking msg ----|                          |
   |   {type: "thinking"}     |                          |
   |                          |                          |
   |<- 8. WS: response msg ----|                          |
   |   {type: "response",     |                          |
   |    messageId: "msg_123"} |                          |
   |                          |                          |
   |-- 9. Display to user ---->|                          |
```

---

## Error Handling

### Frontend Error Scenarios

| Scenario | Action |
|----------|--------|
| Network error on POST | Show error to user, allow retry |
| WebSocket disconnected | Show connection status, attempt reconnect |
| No response received after 30s | Show timeout error, allow retry |
| Duplicate response detected | Silently ignore, log to console |

### Backend Error Scenarios

| Scenario | Response |
|----------|----------|
| Invalid messageId format | 400 Bad Request |
| Missing required fields | 400 Bad Request |
| Agent processing error | 500 Internal Server Error + WebSocket error message |
| Rate limit exceeded | Send error message via WebSocket |

---

## Testing Requirements

### Frontend Tests

- [ ] Message ID generation is unique
- [ ] Deduplication prevents duplicate messages
- [ ] Session ID persists across page refresh
- [ ] WebSocket reconnection works
- [ ] Error states display correctly

### Backend Tests

- [ ] Duplicate messageIds are rejected
- [ ] Message tracking works correctly
- [ ] Session persistence works
- [ ] All WebSocket messages include messageId
- [ ] Error handling sends proper error messages

### Integration Tests

- [ ] End-to-end message flow works
- [ ] Message IDs match across frontend/backend
- [ ] No duplicate responses in UI
- [ ] Session context maintained across messages

---

## Version History

| Version | Date | Changes | Breaking |
|---------|------|---------|----------|
| 1.0.0 | 2025-10-25 | Initial API contract | N/A |

---

## Breaking Changes Policy

1. **Major version increment**: All breaking changes MUST increment major version (e.g., 1.0.0 → 2.0.0)
2. **Notification**: Notify both teams 1 week before breaking changes
3. **Backward compatibility**: Maintain backward compatibility for 1 version cycle
4. **Documentation**: Update this document BEFORE implementing changes

---

## Contact & Support

- **Backend Team**: Python/FastAPI developers
- **Frontend Team**: Next.js developers
- **Questions**: Create GitHub issue with `api-contract` label
- **Changes**: Require PR review from both teams
