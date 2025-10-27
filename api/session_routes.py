"""
Session API Routes

Provides REST endpoints for session management operations.
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from pydantic import BaseModel
import logging

from src.services.session_service import get_session_service
from src.services.memory_buffer_manager import get_memory_buffer_manager
from src.services.supabase_service import get_supabase_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""
    user_id: str
    title: Optional[str] = "New Chat"


class UpdateSessionRequest(BaseModel):
    """Request model for updating a session."""
    title: Optional[str] = None


class AddMessageRequest(BaseModel):
    """Request model for adding a message."""
    message_id: str
    role: str  # 'user' or 'agent'
    content: str
    tokens: Optional[int] = 0
    metadata: Optional[dict] = None


# ============================================================================
# SESSION CRUD ENDPOINTS
# ============================================================================

@router.post("/")
async def create_session(
    request: CreateSessionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Create a new session.
    
    Args:
        request: Session creation parameters
        authorization: Optional JWT token
        
    Returns:
        Created session data
    """
    try:
        # Verify user if token provided
        if authorization:
            supabase = get_supabase_service()
            user = supabase.verify_token(authorization.replace("Bearer ", ""))
            if not user:
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Create session
        session_service = get_session_service()
        session = session_service.create_session_for_user(
            user_id=request.user_id,
            title=request.title
        )
        
        logger.info(f"Session created: {session.get('session_id')}")
        
        return {
            "status": "success",
            "session": session
        }
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get session by ID.
    
    Args:
        session_id: Session identifier
        authorization: Optional JWT token
        
    Returns:
        Session data
    """
    try:
        session_service = get_session_service()
        session = session_service.get_or_create_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "session": session
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_sessions(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    authorization: Optional[str] = Header(None)
):
    """
    List sessions for a user.
    
    Args:
        user_id: User identifier
        limit: Maximum sessions to return
        offset: Number of sessions to skip
        authorization: Optional JWT token
        
    Returns:
        List of sessions
    """
    try:
        session_service = get_session_service()
        sessions = session_service.list_user_sessions(user_id, limit, offset)
        
        return {
            "status": "success",
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Update session.
    
    Args:
        session_id: Session identifier
        request: Update parameters
        authorization: Optional JWT token
        
    Returns:
        Success status
    """
    try:
        session_service = get_session_service()
        
        if request.title:
            success = session_service.update_session_title(session_id, request.title)
            
            if not success:
                raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "message": "Session updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Delete session.
    
    Args:
        session_id: Session identifier
        authorization: Optional JWT token
        
    Returns:
        Success status
    """
    try:
        session_service = get_session_service()
        success = session_service.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "message": "Session deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MESSAGE ENDPOINTS
# ============================================================================

@router.post("/{session_id}/messages")
async def add_message(
    session_id: str,
    request: AddMessageRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Add message to session.
    
    Args:
        session_id: Session identifier
        request: Message parameters
        authorization: Optional JWT token
        
    Returns:
        Success status
    """
    try:
        session_service = get_session_service()
        success = session_service.add_message_to_session(
            session_id=session_id,
            message_id=request.message_id,
            role=request.role,
            content=request.content,
            tokens=request.tokens or 0,
            metadata=request.metadata
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "message": "Message added"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 100,
    authorization: Optional[str] = Header(None)
):
    """
    Get messages for session.
    
    Args:
        session_id: Session identifier
        limit: Maximum messages to return
        authorization: Optional JWT token
        
    Returns:
        List of messages
    """
    try:
        session_service = get_session_service()
        messages = session_service.get_session_messages(session_id, limit)
        
        return {
            "status": "success",
            "messages": messages,
            "count": len(messages)
        }
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MEMORY BUFFER ENDPOINTS
# ============================================================================

@router.get("/{session_id}/buffer")
async def get_memory_buffer(
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get memory buffer for session.
    
    Args:
        session_id: Session identifier
        authorization: Optional JWT token
        
    Returns:
        Memory buffer with stats
    """
    try:
        buffer_manager = get_memory_buffer_manager()
        buffer = buffer_manager.get_buffer_for_session(session_id)
        stats = buffer_manager.get_buffer_stats(buffer)
        
        return {
            "status": "success",
            "buffer": {
                "recent_message_count": len(buffer.recent_messages),
                "has_summary": buffer.summary is not None,
                "total_messages": buffer.message_count,
                "total_tokens": buffer.total_tokens
            },
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get memory buffer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/context")
async def get_formatted_context(
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get formatted context for LLM.
    
    Args:
        session_id: Session identifier
        authorization: Optional JWT token
        
    Returns:
        Formatted context string
    """
    try:
        buffer_manager = get_memory_buffer_manager()
        buffer = buffer_manager.get_buffer_for_session(session_id)
        context = buffer_manager.format_buffer_for_llm(buffer)
        
        return {
            "status": "success",
            "context": context,
            "token_count": buffer.total_tokens
        }
    except Exception as e:
        logger.error(f"Failed to get formatted context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get("/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get session summary.
    
    Args:
        session_id: Session identifier
        authorization: Optional JWT token
        
    Returns:
        Session summary
    """
    try:
        session_service = get_session_service()
        summary = session_service.get_session_summary(session_id)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "status": "success",
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
