# Session Management Architecture

**Version:** 2.0  
**Last Updated:** October 2025  
**Status:** 🚧 In Progress

## Overview

This document outlines the session management architecture for KaryaKarta, including memory buffer strategies, token management, and database schema design for multi-user, production-ready deployment.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Memory Buffer Strategy](#memory-buffer-strategy)
3. [Token Management](#token-management)
4. [Database Schema](#database-schema)
5. [Session Lifecycle](#session-lifecycle)
6. [Message Summarization](#message-summarization)
7. [Implementation Details](#implementation-details)

---

## Architecture Overview

### Current State

- Single-user sessions stored in localStorage
- LangGraph checkpoints in SQLite
- No persistent conversation history across sessions
- No memory buffer management

### Target State

- Multi-user sessions with Supabase PostgreSQL
- Persistent conversation history
- Memory buffer with token limits
- Message summarization for long conversations
- Real-time session synchronization

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   SESSION ARCHITECTURE                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User Request                                            │
│       ↓                                                  │
│  Frontend (Session Context)                              │
│       ↓                                                  │
│  Session API                                             │
│       ↓                                                  │
│  Backend (Session Service)                               │
│       ↓                                                  │
│  Memory Buffer Manager                                   │
│  ├── Recent Messages (Last 10)                           │
│  ├── Summarized Messages (11-50)                         │
│  └── Archived Messages (50+)                             │
│       ↓                                                  │
│  LangGraph Agent (with context window)                   │
│       ↓                                                  │
│  Supabase PostgreSQL                                     │
│  ├── Sessions Table                                      │
│  ├── Messages Table                                      │
│  └── Checkpoints Table                                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Memory Buffer Strategy

### Three-Tier Memory System

```
┌─────────────────────────────────────────────────────────┐
│                    MEMORY TIERS                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Tier 1: Recent Messages (Last 10)                       │
│  ├── Storage: In-memory + Database                       │
│  ├── Sent to Model: YES (full content)                   │
│  ├── Token Budget: ~5K-10K tokens                        │
│  └── Purpose: Active conversation context                │
│                                                          │
│  Tier 2: Summarized History (11-50)                      │
│  ├── Storage: Database (with summaries)                  │
│  ├── Sent to Model: YES (compressed summaries)           │
│  ├── Token Budget: ~2K-5K tokens                         │
│  └── Purpose: Recent context awareness                   │
│                                                          │
│  Tier 3: Archived Messages (50+)                         │
│  ├── Storage: Database only                              │
│  ├── Sent to Model: NO                                   │
│  ├── Token Budget: N/A                                   │
│  └── Purpose: Historical record, searchable              │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Configuration

```python
MEMORY_CONFIG = {
    "recent_messages": 10,          # Last N full messages
    "summary_messages": 40,         # Next N as summaries
    "max_tokens": 30000,           # Hard token limit
    "summarize_threshold": 50,     # Start summarizing after N messages
    "archive_threshold": 100,      # Move to archive after N messages
}
```

### Token Budget Breakdown

| Component | Token Estimate | Notes |
|-----------|---------------|-------|
| System Prompt | ~500-1K | Agent instructions |
| Tool Definitions | ~1K-2K | Tool schemas |
| Recent Messages (10) | ~5K-7K | Full message content |
| Summarized Messages (40) | ~2K-3K | Compressed summaries |
| **Total Context** | **~10K-13K** | Safe margin for 1M context window |

---

## Token Management

### Token Counting

```python
from tiktoken import encoding_for_model

class TokenCounter:
    """Count tokens for different model types."""
    
    def __init__(self, model: str = "gpt-4"):
        self.encoder = encoding_for_model(model)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))
    
    def count_message_tokens(self, messages: list) -> int:
        """Count tokens in message list."""
        total = 0
        for msg in messages:
            # Add message overhead (role, metadata)
            total += 4  # Message formatting tokens
            total += self.count_tokens(msg.get("content", ""))
        return total
```

### Enforcement Strategy

1. **Soft Limit** (25K tokens): Trigger summarization
2. **Hard Limit** (30K tokens): Drop oldest summaries
3. **Emergency Limit** (35K tokens): Error, clear history

### Token Optimization

- Cache token counts to avoid recalculation
- Summarize in batches (every 10 messages)
- Compress JSON metadata
- Remove unnecessary whitespace

---

## Database Schema

### Tables Overview

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions table
CREATE TABLE public.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Messages table
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    message_id TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    tokens INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_summarized BOOLEAN DEFAULT FALSE,
    summary TEXT
);

-- Message summaries table (for batch summarization)
CREATE TABLE public.message_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    start_index INTEGER NOT NULL,
    end_index INTEGER NOT NULL,
    summary TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX idx_sessions_updated_at ON public.sessions(updated_at DESC);
CREATE INDEX idx_sessions_archived ON public.sessions(is_archived, updated_at DESC);
CREATE INDEX idx_messages_session_id ON public.messages(session_id);
CREATE INDEX idx_messages_created_at ON public.messages(created_at DESC);
CREATE INDEX idx_message_summaries_session_id ON public.message_summaries(session_id);
```

### Row Level Security (RLS)

```sql
-- Enable RLS
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_summaries ENABLE ROW LEVEL SECURITY;

-- Sessions policies
CREATE POLICY "Users can view own sessions"
    ON public.sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions"
    ON public.sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions"
    ON public.sessions FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions"
    ON public.sessions FOR DELETE
    USING (auth.uid() = user_id);

-- Messages policies
CREATE POLICY "Users can view own messages"
    ON public.messages FOR SELECT
    USING (
        session_id IN (
            SELECT id FROM public.sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own messages"
    ON public.messages FOR INSERT
    WITH CHECK (
        session_id IN (
            SELECT id FROM public.sessions WHERE user_id = auth.uid()
        )
    );

-- Similar policies for message_summaries
```

---

## Session Lifecycle

### 1. Session Creation

```python
def create_session(user_id: str, title: str = "New Chat") -> Session:
    """Create a new session."""
    session_id = f"session_{user_id}_{int(time.time())}"
    
    session = supabase.table('sessions').insert({
        'user_id': user_id,
        'session_id': session_id,
        'title': title,
        'message_count': 0,
        'total_tokens': 0
    }).execute()
    
    return session.data[0]
```

### 2. Message Addition

```python
def add_message(session_id: str, role: str, content: str) -> Message:
    """Add message to session."""
    # Count tokens
    token_count = token_counter.count_tokens(content)
    
    # Insert message
    message = supabase.table('messages').insert({
        'session_id': session_id,
        'message_id': f"msg_{int(time.time())}_{random_string()}",
        'role': role,
        'content': content,
        'tokens': token_count
    }).execute()
    
    # Update session
    supabase.table('sessions').update({
        'message_count': supabase.rpc('increment', {'value': 1}),
        'total_tokens': supabase.rpc('increment', {'value': token_count}),
        'updated_at': datetime.now().isoformat()
    }).eq('id', session_id).execute()
    
    return message.data[0]
```

### 3. Context Window Retrieval

```python
def get_context_window(session_id: str) -> List[Message]:
    """Get optimized context window for LLM."""
    # Get recent messages (full)
    recent = get_recent_messages(session_id, limit=10)
    
    # Get summarized messages
    summaries = get_message_summaries(session_id, limit=40)
    
    # Combine and check token limit
    context = recent + summaries
    total_tokens = sum(msg.tokens for msg in context)
    
    if total_tokens > MEMORY_CONFIG['max_tokens']:
        # Trim summaries if needed
        context = enforce_token_limit(context)
    
    return context
```

### 4. Session Archival

```python
def archive_session(session_id: str):
    """Archive old session."""
    supabase.table('sessions').update({
        'is_archived': True,
        'updated_at': datetime.now().isoformat()
    }).eq('id', session_id).execute()
```

---

## Message Summarization

### Summarization Strategy

**When to Summarize:**
- After every 10 messages
- When token count exceeds threshold
- On session close (optional)

**Summarization Prompt:**
```
Summarize the following conversation exchange concisely:

User: {user_message}
Agent: {agent_response}

Summary (max 50 words):
```

### Batch Summarization

```python
def summarize_messages(session_id: str, start_idx: int, end_idx: int) -> str:
    """Summarize a batch of messages."""
    messages = get_messages_range(session_id, start_idx, end_idx)
    
    # Format messages for summarization
    text = format_messages_for_summary(messages)
    
    # Use LLM to summarize
    summary = llm.invoke(f"Summarize concisely: {text}")
    
    # Store summary
    token_count = token_counter.count_tokens(summary)
    supabase.table('message_summaries').insert({
        'session_id': session_id,
        'start_index': start_idx,
        'end_index': end_idx,
        'summary': summary,
        'token_count': token_count
    }).execute()
    
    # Mark messages as summarized
    for msg in messages:
        mark_message_summarized(msg.id)
    
    return summary
```

---

## Implementation Details

### Memory Buffer Manager

```python
class MemoryBufferManager:
    """Manages memory buffer for agent conversations."""
    
    def __init__(self, config: dict):
        self.config = config
        self.token_counter = TokenCounter()
    
    def get_context_window(self, session_id: str) -> List[Message]:
        """Get optimized context window."""
        pass
    
    def enforce_token_limit(self, messages: List[Message]) -> List[Message]:
        """Enforce token limit on messages."""
        pass
    
    def should_summarize(self, session_id: str) -> bool:
        """Check if summarization is needed."""
        pass
    
    def summarize_batch(self, session_id: str) -> str:
        """Summarize a batch of messages."""
        pass
```

### Session Service

```python
class SessionService:
    """Service for session CRUD operations."""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    def create_session(self, user_id: str, title: str) -> Session:
        """Create new session."""
        pass
    
    def get_session(self, session_id: str) -> Session:
        """Get session details."""
        pass
    
    def list_sessions(self, user_id: str, limit: int = 50) -> List[Session]:
        """List user's sessions."""
        pass
    
    def update_session(self, session_id: str, updates: dict) -> Session:
        """Update session."""
        pass
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        pass
    
    def add_message(self, session_id: str, message: dict) -> Message:
        """Add message to session."""
        pass
    
    def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """Get session messages."""
        pass
```

---

## Performance Considerations

### Caching Strategy

- Cache recent messages in memory
- Cache token counts
- Cache summaries for 5 minutes

### Query Optimization

- Use indexes on frequently queried columns
- Limit query results
- Use pagination for large result sets
- Use database functions for aggregations

### Scalability

- Horizontal scaling via Supabase
- Connection pooling
- Async operations for non-blocking I/O
- Background workers for summarization

---

## Monitoring & Metrics

### Key Metrics

- Average tokens per session
- Message count distribution
- Summarization frequency
- Query performance
- Cache hit rate

### Alerts

- Token limit exceeded
- Summarization failures
- Database connection issues
- Memory usage warnings

---

## Future Enhancements

1. **Semantic Search**: Search messages by meaning, not just keywords
2. **Auto-Tagging**: Automatically tag sessions by topic
3. **Export**: Export session history to PDF/JSON
4. **Collaborative Sessions**: Share sessions between users
5. **Voice Messages**: Support audio messages with transcription
6. **Smart Summarization**: Use better models for summarization

---

## References

- [LangGraph Memory Documentation](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
- [Supabase Database Documentation](https://supabase.com/docs/guides/database)
- [Token Counting with Tiktoken](https://github.com/openai/tiktoken)
