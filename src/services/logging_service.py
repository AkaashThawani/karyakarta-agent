"""
Logging Service - PRIORITY 1

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Centralized logging service for sending messages to frontend via WebSocket.
Extracts and improves the send_log_to_socket() function from agent_logic.py

Usage:
    from src.services.logging_service import LoggingService
    from src.core.config import settings
    
    logger = LoggingService(settings.logging_url)
    logger.log("Processing...", "status", message_id="msg_123")
"""

import requests
from datetime import datetime
from typing import Optional, Literal
import re
from src.models.message import AgentMessage


class LoggingService:
    """Service for sending structured logs to frontend via WebSocket with response sanitization."""
    
    def __init__(self, websocket_url: str):
        """
        Initialize logging service.
        
        Args:
            websocket_url: URL of the WebSocket logging endpoint
        """
        self.url = websocket_url
    
    @staticmethod
    def sanitize_message(message: str, max_length: int = 10000) -> str:
        """
        Sanitize message before sending to frontend.
        
        Removes:
        - Null bytes
        - Control characters (except newlines and tabs)
        - Excessive whitespace
        
        Limits:
        - Maximum length
        
        Args:
            message: Message to sanitize
            max_length: Maximum message length
            
        Returns:
            Sanitized message
        """
        # Remove null bytes
        message = message.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        message = ''.join(
            char for char in message 
            if char in ('\n', '\t') or (ord(char) >= 32 and ord(char) != 127)
        )
        
        # Collapse multiple newlines into max 2
        message = re.sub(r'\n{3,}', '\n\n', message)
        
        # Collapse multiple spaces into single space
        message = re.sub(r' {2,}', ' ', message)
        
        # Trim whitespace
        message = message.strip()
        
        # Enforce length limit
        if len(message) > max_length:
            message = message[:max_length] + "\n\n[Response truncated due to length]"
        
        return message
    
    def log(
        self,
        message: str,
        message_type: Literal["status", "thinking", "response", "error"] = "status",
        message_id: Optional[str] = None
    ) -> bool:
        """
        Send a log message to the frontend via WebSocket.
        
        Messages are sanitized before sending to prevent XSS and ensure clean output.
        
        Args:
            message: The message content
            message_type: Type of message (status, thinking, response, error)
            message_id: Optional message ID to link with request
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Sanitize message before sending
            sanitized_message = self.sanitize_message(message)
            
            # Create structured message using Pydantic model
            agent_message = AgentMessage(
                type=message_type,
                message=sanitized_message,
                timestamp=datetime.now().isoformat(),
                messageId=message_id
            )
            
            # Send to WebSocket endpoint
            response = requests.post(
                self.url,
                json=agent_message.model_dump(),
                timeout=5
            )
            
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            # Log to console but don't crash
            print(f"[LoggingService] Could not send log to frontend: {e}")
            return False
        except Exception as e:
            print(f"[LoggingService] Unexpected error: {e}")
            return False
    
    def status(self, message: str, message_id: Optional[str] = None):
        """Convenience method for status messages."""
        return self.log(message, "status", message_id)
    
    def thinking(self, message: str, message_id: Optional[str] = None):
        """Convenience method for thinking messages."""
        return self.log(message, "thinking", message_id)
    
    def response(self, message: str, message_id: Optional[str] = None):
        """Convenience method for response messages."""
        return self.log(message, "response", message_id)
    
    def error(self, message: str, message_id: Optional[str] = None):
        """Convenience method for error messages."""
        return self.log(message, "error", message_id)
