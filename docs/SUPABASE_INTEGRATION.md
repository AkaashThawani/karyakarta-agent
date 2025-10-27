# Supabase Integration Guide

**Version:** 2.0  
**Last Updated:** October 2025  
**Status:** 🚧 In Progress

## Overview

This document provides a comprehensive guide for integrating Supabase into KaryaKarta for multi-user authentication, PostgreSQL database, and real-time features.

## Table of Contents

1. [Why Supabase?](#why-supabase)
2. [Setup Instructions](#setup-instructions)
3. [Database Schema](#database-schema)
4. [Authentication](#authentication)
5. [Row Level Security](#row-level-security)
6. [Backend Integration](#backend-integration)
7. [Frontend Integration](#frontend-integration)
8. [Migration from SQLite](#migration-from-sqlite)
9. [Best Practices](#best-practices)

---

## Why Supabase?

### Benefits Over SQLite

| Feature | SQLite | Supabase PostgreSQL |
|---------|--------|-------------------|
| Multi-user | ❌ No | ✅ Yes |
| Authentication | ❌ No | ✅ Built-in |
| Real-time | ❌ No | ✅ Yes |
| Scalability | ❌ Limited | ✅ Horizontal scaling |
| Backups | ❌ Manual | ✅ Automatic |
| Cloud-ready | ❌ No | ✅ Yes |
| Cost (dev) | ✅ Free | ✅ Free (500MB) |

### Use Cases

✅ **Perfect for:**
- Multi-user applications
- Production deployments
- Real-time features
- Cloud deployment
- Team collaboration

❌ **Not needed for:**
- Single-user local apps
- Offline-first apps
- Simple prototypes

---

## Setup Instructions

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Click "Start your project"
3. Sign up/login with GitHub
4. Create new organization
5. Create new project:
   - **Name:** karyakarta-production
   - **Database Password:** (generate strong password)
   - **Region:** Choose closest to your users
   - **Plan:** Free tier (for development)

### 2. Get API Keys

After project creation, go to **Project Settings** → **API**:

```bash
# Public (Anon) Key - Safe to use in frontend
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Service Role Key - NEVER expose to frontend (backend only)
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Database URL (for direct connections)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxxx.supabase.co:5432/postgres
```

### 3. Configure Environment Variables

**Backend (`.env`):**
```bash
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# LLM
GOOGLE_API_KEY=your_google_api_key

# Server
PORT=8000
LOGGING_URL=http://localhost:3000/api/socket/log
```

**Frontend (`.env.local`):**
```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. Install Dependencies

**Backend:**
```bash
cd karyakarta-agent
pip install supabase-py postgrest-py
```

**Frontend:**
```bash
cd karyakarta-ai
npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
```

---

## Database Schema

### Complete SQL Setup

Run this SQL in Supabase SQL Editor (**Dashboard** → **SQL Editor** → **New Query**):

```sql
-- ============================================================================
-- KARYAKARTA DATABASE SCHEMA
-- Version: 2.0
-- Description: Complete schema for session management and authentication
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    is_archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT valid_message_count CHECK (message_count >= 0),
    CONSTRAINT valid_token_count CHECK (total_tokens >= 0)
);

-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    message_id TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    tokens INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_summarized BOOLEAN DEFAULT FALSE,
    summary TEXT,
    
    -- Constraints
    CONSTRAINT valid_tokens CHECK (tokens >= 0),
    CONSTRAINT non_empty_content CHECK (length(trim(content)) > 0)
);

-- ============================================================================
-- MESSAGE SUMMARIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.message_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES public.sessions(id) ON DELETE CASCADE,
    start_index INTEGER NOT NULL,
    end_index INTEGER NOT NULL,
    summary TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_indices CHECK (end_index > start_index),
    CONSTRAINT valid_summary_tokens CHECK (token_count > 0)
);

-- ============================================================================
-- LANGGRAPH CHECKPOINTS (Separate Schema)
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS langgraph;

CREATE TABLE IF NOT EXISTS langgraph.checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_id TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
    ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at 
    ON public.sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_archived 
    ON public.sessions(is_archived, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id 
    ON public.sessions(session_id);

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_session_id 
    ON public.messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at 
    ON public.messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_message_id 
    ON public.messages(message_id);
CREATE INDEX IF NOT EXISTS idx_messages_role 
    ON public.messages(role);

-- Full-text search index for messages
CREATE INDEX IF NOT EXISTS idx_messages_content_search 
    ON public.messages USING gin(to_tsvector('english', content));

-- Message summaries indexes
CREATE INDEX IF NOT EXISTS idx_message_summaries_session_id 
    ON public.message_summaries(session_id);

-- Checkpoints indexes
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
    ON langgraph.checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
    ON langgraph.checkpoints(created_at DESC);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update session timestamp
CREATE OR REPLACE FUNCTION update_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.sessions
    SET updated_at = NOW(),
        last_message_at = NOW()
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to increment message count
CREATE OR REPLACE FUNCTION increment_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.sessions
    SET message_count = message_count + 1,
        total_tokens = total_tokens + COALESCE(NEW.tokens, 0)
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to auto-generate session title
CREATE OR REPLACE FUNCTION generate_session_title()
RETURNS TRIGGER AS $$
BEGIN
    -- If this is the first message and session has default title
    IF (SELECT message_count FROM public.sessions WHERE id = NEW.session_id) = 0 THEN
        IF (SELECT title FROM public.sessions WHERE id = NEW.session_id) = 'New Chat' THEN
            UPDATE public.sessions
            SET title = CASE
                WHEN LENGTH(NEW.content) > 50 
                THEN LEFT(NEW.content, 47) || '...'
                ELSE NEW.content
            END
            WHERE id = NEW.session_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger to update session timestamp on new message
DROP TRIGGER IF EXISTS trigger_update_session_timestamp ON public.messages;
CREATE TRIGGER trigger_update_session_timestamp
    AFTER INSERT ON public.messages
    FOR EACH ROW
    EXECUTE FUNCTION update_session_timestamp();

-- Trigger to increment message count
DROP TRIGGER IF EXISTS trigger_increment_message_count ON public.messages;
CREATE TRIGGER trigger_increment_message_count
    AFTER INSERT ON public.messages
    FOR EACH ROW
    EXECUTE FUNCTION increment_message_count();

-- Trigger to auto-generate title
DROP TRIGGER IF EXISTS trigger_generate_session_title ON public.messages;
CREATE TRIGGER trigger_generate_session_title
    AFTER INSERT ON public.messages
    FOR EACH ROW
    WHEN (NEW.role = 'user')
    EXECUTE FUNCTION generate_session_title();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_summaries ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Users can view own sessions" ON public.sessions;
DROP POLICY IF EXISTS "Users can insert own sessions" ON public.sessions;
DROP POLICY IF EXISTS "Users can update own sessions" ON public.sessions;
DROP POLICY IF EXISTS "Users can delete own sessions" ON public.sessions;
DROP POLICY IF EXISTS "Users can view own messages" ON public.messages;
DROP POLICY IF EXISTS "Users can insert own messages" ON public.messages;
DROP POLICY IF EXISTS "Users can view own summaries" ON public.message_summaries;
DROP POLICY IF EXISTS "Users can insert own summaries" ON public.message_summaries;

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

-- Message summaries policies
CREATE POLICY "Users can view own summaries"
    ON public.message_summaries FOR SELECT
    USING (
        session_id IN (
            SELECT id FROM public.sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own summaries"
    ON public.message_summaries FOR INSERT
    WITH CHECK (
        session_id IN (
            SELECT id FROM public.sessions WHERE user_id = auth.uid()
        )
    );

-- ============================================================================
-- STORAGE BUCKETS (Optional - for file uploads)
-- ============================================================================

-- Create storage bucket for user uploads
INSERT INTO storage.buckets (id, name, public)
VALUES ('user-uploads', 'user-uploads', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies
CREATE POLICY "Users can upload own files"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can view own files"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Insert test user (you'll need to sign up through Supabase Auth UI first)
-- Then run this to create a test session:
-- 
-- INSERT INTO public.sessions (user_id, session_id, title)
-- VALUES (
--     '<your-user-id>',
--     'session_test_' || extract(epoch from now())::text,
--     'Test Session'
-- );

-- ============================================================================
-- VIEWS (Optional - for analytics)
-- ============================================================================

-- View for session statistics
CREATE OR REPLACE VIEW public.session_stats AS
SELECT 
    s.id,
    s.session_id,
    s.title,
    s.created_at,
    s.updated_at,
    s.message_count,
    s.total_tokens,
    COUNT(m.id) as actual_message_count,
    SUM(m.tokens) as actual_token_count
FROM public.sessions s
LEFT JOIN public.messages m ON s.id = m.session_id
GROUP BY s.id, s.session_id, s.title, s.created_at, s.updated_at, s.message_count, s.total_tokens;

-- ============================================================================
-- GRANTS (Ensure proper permissions)
-- ============================================================================

-- Grant necessary permissions to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- Grant permissions for LangGraph schema
GRANT USAGE ON SCHEMA langgraph TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA langgraph TO authenticated;

-- ============================================================================
-- COMPLETE!
-- ============================================================================

-- Verify setup
SELECT 
    'Setup complete! Tables created:' as status,
    COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public' 
AND table_name IN ('sessions', 'messages', 'message_summaries');
```

---

## Authentication

### Email/Password Authentication

**1. Enable Email Auth in Supabase:**
- Go to **Authentication** → **Providers**
- Enable **Email** provider
- Configure email templates (optional)

**2. Backend Auth Middleware:**

```python
# karyakarta-agent/api/auth_middleware.py

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
import os

security = HTTPBearer()
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify JWT token from Supabase."""
    token = credentials.credentials
    
    try:
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        return user.user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Usage in routes:
from fastapi import Depends

@router.get("/protected")
async def protected_route(user=Depends(verify_token)):
    return {"message": f"Hello {user.email}"}
```

**3. Frontend Auth Context:**

```typescript
// karyakarta-ai/src/contexts/auth-context.tsx

import { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { User } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check active session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  };

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
```

---

## Row Level Security

### Understanding RLS

Row Level Security (RLS) ensures users can only access their own data. Enabled policies automatically filter queries.

### Policy Examples

```sql
-- View only own sessions
CREATE POLICY "users_view_own_sessions"
ON sessions FOR SELECT
USING (auth.uid() = user_id);

-- Insert only own sessions
CREATE POLICY "users_insert_own_sessions"
ON sessions FOR INSERT
WITH CHECK (auth.uid() = user_id);
```

### Testing RLS

```sql
-- Test as specific user
SET request.jwt.claim.sub = '<user-id>';

-- Should only see own sessions
SELECT * FROM sessions;
```

---

## Backend Integration

See `karyakarta-agent/src/services/supabase_service.py` for full implementation.

---

## Frontend Integration

See `karyakarta-ai/src/lib/supabase.ts` for full implementation.

---

## Migration from SQLite

### Migration Strategy

1. **Export SQLite data** (if any exists)
2. **Transform to Supabase format**
3. **Import via Supabase client**
4. **Verify data integrity**
5. **Update code to use Supabase**

---

## Best Practices

1. **Never expose service role key** in frontend
2. **Always use RLS** policies
3. **Validate input** before database operations
4. **Use prepared statements** (automatic with Supabase client)
5. **Handle errors gracefully**
6. **Monitor usage** via Supabase dashboard
7. **Backup regularly** (automatic with Supabase)
8. **Use connection pooling** for backend
9. **Cache frequently accessed data**
10. **Index foreign keys**

---

## Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Python Client](https://github.com/supabase-community/supabase-py)
- [Supabase JS Client](https://github.com/supabase/supabase-js)
- [RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)
