"""
Message Data Models - PRIORITY 1

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Pydantic models for all message types with validation.
Matches TypeScript types in frontend (karyakarta-ai/src/types/api.ts)

Usage:
    from src.models.message import TaskRequest, TaskResponse, AgentMessage
    
    request = TaskRequest(
        prompt="Hello",
        messageId="msg_123",
        sessionId="session_456"
    )
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
import re


class TaskRequest(BaseModel):
    """Request to execute an agent task with input validation."""
    prompt: str = Field(..., description="User's query", min_length=1, max_length=5000)
    messageId: str = Field(..., description="Unique message identifier", pattern=r'^msg_\d+_[a-z0-9]+$')
    sessionId: Optional[str] = Field(default="default", description="Session identifier", pattern=r'^[a-zA-Z0-9_-]+$')
    
    @field_validator('prompt')
    @classmethod
    def sanitize_prompt(cls, v: str) -> str:
        """Sanitize prompt to remove potentially harmful content."""
        # Remove null bytes
        v = v.replace('\x00', '')
        
        # Remove other control characters except newlines and tabs
        v = ''.join(char for char in v if char == '\n' or char == '\t' or not char.isprintable() or char.isprintable())
        
        # Trim whitespace
        v = v.strip()
        
        # Ensure not empty after sanitization
        if not v:
            raise ValueError("Prompt cannot be empty")
        
        # Length check
        if len(v) > 5000:
            raise ValueError("Prompt too long (max 5000 characters)")
        
        return v
    
    @field_validator('messageId')
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        """Validate message ID format."""
        if not re.match(r'^msg_\d+_[a-z0-9]+$', v):
            raise ValueError("Invalid messageId format. Expected: msg_{timestamp}_{random}")
        return v
    
    @field_validator('sessionId')
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> str:
        """Validate and sanitize session ID."""
        if v is None:
            return "default"
        
        # Only allow alphanumeric, underscore, hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Invalid sessionId format. Only alphanumeric, underscore, and hyphen allowed")
        
        if len(v) > 100:
            raise ValueError("SessionId too long (max 100 characters)")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Find restaurants near me",
                "messageId": "msg_1729876543210_abc123",
                "sessionId": "session_user_1729876543210"
            }
        }


class TaskResponse(BaseModel):
    """Response from task execution."""
    status: Literal["success", "error", "already_processing"]
    messageId: str
    sessionId: str
    error: Optional[str] = None
    message: str = "Agent task has been initiated in the background."
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "messageId": "msg_1729876543210_abc123",
                "sessionId": "session_user_1729876543210",
                "message": "Agent task has been initiated in the background."
            }
        }


class AgentMessage(BaseModel):
    """WebSocket message from agent to frontend."""
    type: Literal["status", "thinking", "response", "error"]
    message: str
    timestamp: str
    messageId: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "response",
                "message": "Here is what I found...",
                "timestamp": "2025-10-25T12:00:00.000Z",
                "messageId": "msg_1729876543210_abc123"
            }
        }
