"""
Session Models

Models for managing agent sessions and conversation state.
Supports session persistence, context tracking, and multi-turn conversations.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    IDLE = "idle"
    COMPLETED = "completed"
    ERROR = "error"


class SessionMessage(BaseModel):
    """
    A message within a session.
    
    Tracks both user and agent messages with metadata.
    """
    
    id: str = Field(description="Unique message identifier")
    role: str = Field(description="Message role: 'user' or 'agent'")
    content: str = Field(description="Message content")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Message timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )


class AgentSession(BaseModel):
    """
    Agent session model for conversation management.
    
    Tracks:
    - Session metadata (ID, timestamps, status)
    - Conversation history
    - Session-specific data
    - User context
    
    Example:
        session = AgentSession(
            session_id="user_123",
            user_id="user_123",
            messages=[
                SessionMessage(id="msg_1", role="user", content="Hello"),
                SessionMessage(id="msg_2", role="agent", content="Hi there!")
            ]
        )
    """
    
    session_id: str = Field(description="Unique session identifier")
    
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier (if multi-user)"
    )
    
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        description="Current session status"
    )
    
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Session creation timestamp"
    )
    
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Last update timestamp"
    )
    
    messages: List[SessionMessage] = Field(
        default_factory=list,
        description="Session message history"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session metadata (tools used, costs, etc.)"
    )
    
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session-specific context data"
    )
    
    def add_message(self, message: SessionMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
    
    def get_message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)
    
    def get_user_message_count(self) -> int:
        """Get user message count."""
        return sum(1 for msg in self.messages if msg.role == "user")
    
    def get_agent_message_count(self) -> int:
        """Get agent message count."""
        return sum(1 for msg in self.messages if msg.role == "agent")
    
    def get_recent_messages(self, limit: int = 10) -> List[SessionMessage]:
        """Get most recent messages."""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
    
    def clear_history(self) -> None:
        """Clear message history."""
        self.messages = []
        self.updated_at = datetime.now().isoformat()
    
    def mark_completed(self) -> None:
        """Mark session as completed."""
        self.status = SessionStatus.COMPLETED
        self.updated_at = datetime.now().isoformat()
    
    def mark_error(self) -> None:
        """Mark session as error."""
        self.status = SessionStatus.ERROR
        self.updated_at = datetime.now().isoformat()
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "session_id": "session_user_123",
                "user_id": "user_123",
                "status": "active",
                "created_at": "2025-10-25T10:00:00",
                "updated_at": "2025-10-25T10:30:00",
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "user",
                        "content": "Hello",
                        "timestamp": "2025-10-25T10:00:00",
                        "metadata": {}
                    }
                ],
                "metadata": {"tools_used": ["search"], "cost": 0.01},
                "context": {}
            }
        }


class SessionSummary(BaseModel):
    """
    Lightweight session summary for listing/management.
    
    Used when full session details aren't needed.
    """
    
    session_id: str
    user_id: Optional[str] = None
    status: SessionStatus
    message_count: int
    created_at: str
    updated_at: str
    last_user_message: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
