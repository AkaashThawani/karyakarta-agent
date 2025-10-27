"""
Session Service - High-level session management

Provides business logic for session operations, building on top of
the Supabase service.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import time
import random
import string
import logging

from src.services.supabase_service import get_supabase_service

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for managing user sessions.
    
    Provides high-level operations for creating, retrieving, and
    managing chat sessions.
    """
    
    def __init__(self):
        """Initialize session service with Supabase client."""
        try:
            self.supabase = get_supabase_service()
            logger.info("Session service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize session service: {e}")
            # Don't raise - allow graceful degradation
            self.supabase = None  # type: ignore
    
    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================
    
    def create_session_for_user(
        self,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for a user.
        
        Args:
            user_id: User identifier
            title: Optional session title
            
        Returns:
            Created session data
        """
        if not self.supabase:
            # Fallback to in-memory session
            return self._create_fallback_session(user_id, title)
        
        try:
            # Generate unique session ID
            session_id = self._generate_session_id(user_id)
            
            # Create session in Supabase
            session = self.supabase.create_session(
                user_id=user_id,
                session_id=session_id,
                title=title or "New Chat"
            )
            
            logger.info(f"Created session {session_id} for user {user_id}")
            return session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return self._create_fallback_session(user_id, title)
    
    def get_or_create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get existing session or create if doesn't exist.
        
        Args:
            session_id: Session identifier
            user_id: User identifier (required for creation)
            
        Returns:
            Session data
        """
        if not self.supabase:
            return self._create_fallback_session(user_id or "default")
        
        try:
            # Try to get existing session
            session = self.supabase.get_session(session_id)
            
            if session:
                return session
            
            # Session doesn't exist, create it
            if not user_id:
                # Extract user_id from session_id format: session_{user}_{timestamp}
                parts = session_id.split('_')
                user_id = parts[1] if len(parts) >= 3 else "default"
            
            return self.supabase.create_session(
                user_id=user_id,
                session_id=session_id,
                title="New Chat"
            )
        except Exception as e:
            logger.error(f"Failed to get or create session: {e}")
            return self._create_fallback_session(user_id or "default")
    
    def list_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all sessions for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum sessions to return
            offset: Number of sessions to skip
            
        Returns:
            List of sessions sorted by updated_at desc
        """
        if not self.supabase:
            return []
        
        try:
            return self.supabase.list_sessions(user_id, limit, offset)
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    def update_session_title(
        self,
        session_id: str,
        title: str
    ) -> bool:
        """
        Update session title.
        
        Args:
            session_id: Session identifier
            title: New title
            
        Returns:
            True if successful
        """
        if not self.supabase:
            return False
        
        try:
            result = self.supabase.update_session(
                session_id,
                {'title': title}
            )
            return result is not None
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        if not self.supabase:
            return False
        
        try:
            return self.supabase.delete_session(session_id)
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    def archive_session(self, session_id: str) -> bool:
        """
        Archive a session (soft delete).
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        if not self.supabase:
            return False
        
        try:
            result = self.supabase.update_session(
                session_id,
                {'is_archived': True}
            )
            return result is not None
        except Exception as e:
            logger.error(f"Failed to archive session: {e}")
            return False
    
    # =========================================================================
    # MESSAGE OPERATIONS
    # =========================================================================
    
    def add_message_to_session(
        self,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a message to a session.
        
        Args:
            session_id: Session identifier
            message_id: Unique message identifier
            role: Message role ('user' or 'agent')
            content: Message content
            tokens: Token count
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        if not self.supabase:
            return False
        
        try:
            result = self.supabase.add_message(
                session_id=session_id,
                message_id=message_id,
                role=role,
                content=content,
                tokens=tokens,
                metadata=metadata
            )
            return result is not None
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            return False
    
    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            
        Returns:
            List of messages ordered by created_at
        """
        if not self.supabase:
            return []
        
        try:
            return self.supabase.get_messages(session_id, limit)
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _generate_session_id(self, user_id: str) -> str:
        """
        Generate a unique session ID.
        
        Format: session_{user_id}_{timestamp}
        
        Args:
            user_id: User identifier
            
        Returns:
            Unique session ID
        """
        timestamp = int(time.time())
        return f"session_{user_id}_{timestamp}"
    
    def _create_fallback_session(
        self,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create fallback in-memory session when Supabase unavailable.
        
        Args:
            user_id: User identifier
            title: Optional title
            
        Returns:
            Session data
        """
        session_id = self._generate_session_id(user_id)
        return {
            'id': ''.join(random.choices(string.ascii_letters, k=16)),
            'user_id': user_id,
            'session_id': session_id,
            'title': title or "New Chat",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'message_count': 0,
            'total_tokens': 0,
            'is_archived': False
        }
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session summary with metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session summary or None
        """
        if not self.supabase:
            return None
        
        try:
            session = self.supabase.get_session(session_id)
            if not session:
                return None
            
            # Return lightweight summary
            return {
                'session_id': session.get('session_id'),
                'title': session.get('title'),
                'message_count': session.get('message_count', 0),
                'created_at': session.get('created_at'),
                'updated_at': session.get('updated_at'),
            }
        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return None


# Global instance
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """
    Get or create the global session service instance.
    
    Returns:
        SessionService instance
    """
    global _session_service
    
    if _session_service is None:
        _session_service = SessionService()
    
    return _session_service
