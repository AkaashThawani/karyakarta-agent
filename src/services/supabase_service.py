"""
Supabase Service - Database and Authentication

Provides a clean interface for interacting with Supabase PostgreSQL database
and authentication services.
"""

from typing import Optional, Dict, Any, List
from supabase import create_client, Client
import os
import logging

logger = logging.getLogger(__name__)


class SupabaseService:
    """
    Service for interacting with Supabase.
    
    Handles database operations, authentication, and real-time subscriptions.
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase client.
        
        Args:
            url: Supabase project URL (defaults to env var)
            key: Supabase service role key (defaults to env var)
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_KEY")
        
        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment"
            )
        
        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================
    
    def create_session(
        self, 
        user_id: str, 
        session_id: str, 
        title: str = "New Chat"
    ) -> Dict[str, Any]:
        """
        Create a new session.
        
        Args:
            user_id: User identifier
            session_id: Unique session identifier
            title: Session title
            
        Returns:
            Created session data
        """
        try:
            response = self.client.table('sessions').insert({
                'user_id': user_id,
                'session_id': session_id,
                'title': title,
                'message_count': 0,
                'total_tokens': 0
            }).execute()
            
            logger.info(f"Session created: {session_id}")
            return response.data[0] if response.data else {}
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier (can be UUID or session_id string)
            
        Returns:
            Session data or None
        """
        # Try session_id field first (for agent string format like session_user_timestamp)
        try:
            response = self.client.table('sessions')\
                .select('*')\
                .eq('session_id', session_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Session found by session_id: {session_id}")
                return response.data[0]
        except Exception as e:
            logger.debug(f"session_id lookup failed for {session_id}: {e}")
        
        # Try id field (for UUID format from frontend)
        try:
            response = self.client.table('sessions')\
                .select('*')\
                .eq('id', session_id)\
                .single()\
                .execute()
            
            if response.data:
                logger.info(f"Session found by id (UUID): {session_id}")
                return response.data
        except Exception as e:
            logger.debug(f"id lookup failed for {session_id}: {e}")
        
        logger.warning(f"Session not found: {session_id}")
        return None
    
    def list_sessions(
        self, 
        user_id: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List user's sessions.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            
        Returns:
            List of sessions
        """
        try:
            response = self.client.table('sessions')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('is_archived', False)\
                .order('updated_at', desc=True)\
                .range(offset, offset + limit - 1)\
                .execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Failed to list sessions for user {user_id}: {e}")
            return []
    
    def update_session(
        self, 
        session_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update session.
        
        Args:
            session_id: Session identifier
            updates: Fields to update
            
        Returns:
            Updated session data or None
        """
        try:
            response = self.client.table('sessions')\
                .update(updates)\
                .eq('session_id', session_id)\
                .execute()
            
            logger.info(f"Session updated: {session_id}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session.
        
        Args:
            session_id: Session identifier (UUID)
            
        Returns:
            True if successful
        """
        try:
            # Frontend sends the UUID (id field), not session_id field
            self.client.table('sessions')\
                .delete()\
                .eq('id', session_id)\
                .execute()
            
            logger.info(f"Session deleted: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    # =========================================================================
    # MESSAGE OPERATIONS
    # =========================================================================
    
    def add_message(
        self,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Add message to session.
        
        Args:
            session_id: Session identifier
            message_id: Unique message identifier
            role: Message role ('user' or 'agent')
            content: Message content
            tokens: Token count
            metadata: Additional metadata
            
        Returns:
            Created message data or None
        """
        try:
            # Get session UUID
            session = self.get_session(session_id)
            if not session:
                logger.error(f"Session not found: {session_id}")
                return None
            
            # Insert message
            response = self.client.table('messages').insert({
                'session_id': session['id'],  # Use UUID
                'message_id': message_id,
                'role': role,
                'content': content,
                'tokens': tokens,
                'metadata': metadata or {}
            }).execute()
            
            logger.info(f"Message added: {message_id} to session {session_id}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            return None
    
    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get messages for session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages
            offset: Number of messages to skip
            
        Returns:
            List of messages
        """
        try:
            # Get session UUID
            session = self.get_session(session_id)
            if not session:
                return []
            
            response = self.client.table('messages')\
                .select('*')\
                .eq('session_id', session['id'])\
                .order('created_at', desc=False)\
                .range(offset, offset + limit - 1)\
                .execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
    
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and get user.
        
        Args:
            token: JWT token
            
        Returns:
            User data or None
        """
        try:
            user = self.client.auth.get_user(token)
            return user.user if user else None
        except Exception as e:
            logger.error(f"Failed to verify token: {e}")
            return None
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def health_check(self) -> bool:
        """
        Check if Supabase connection is healthy.
        
        Returns:
            True if healthy
        """
        try:
            # Try a simple query
            self.client.table('sessions').select('id').limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return False


# Global instance (singleton pattern)
_supabase_service: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """
    Get or create the global Supabase service instance.
    
    Returns:
        SupabaseService instance
    """
    global _supabase_service
    
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    
    return _supabase_service
