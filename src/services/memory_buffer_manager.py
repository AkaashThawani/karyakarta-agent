"""
Memory Buffer Manager - Smart Context Management

Implements the 3-tier memory system:
- Tier 1: Recent messages (10 most recent, full content)
- Tier 2: Summarized messages (40 older messages, summarized)
- Tier 3: Archived messages (historical, not loaded)

Target: Stay under 30K tokens with ~10-13K actual usage
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import tiktoken
import logging

from src.services.session_service import get_session_service

logger = logging.getLogger(__name__)


@dataclass
class MemoryBuffer:
    """Container for memory buffer state."""
    recent_messages: List[Dict[str, Any]]  # Tier 1: Full messages
    summary: Optional[str]  # Tier 2: Summarized older messages
    total_tokens: int
    message_count: int


class MemoryBufferManager:
    """
    Manages conversation context with intelligent memory buffer strategy.
    
    Uses a 3-tier system to stay under token limits while maintaining
    context quality.
    """
    
    def __init__(
        self,
        max_tokens: int = 30000,
        target_tokens: int = 13000,
        recent_message_count: int = 10
    ):
        """
        Initialize memory buffer manager.
        
        Args:
            max_tokens: Hard token limit (30K for Gemini)
            target_tokens: Target usage (~13K for buffer)
            recent_message_count: Number of recent messages to keep (Tier 1)
        """
        self.max_tokens = max_tokens
        self.target_tokens = target_tokens
        self.recent_message_count = recent_message_count
        
        # Initialize tokenizer (OpenAI tokenizer as approximation)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"Failed to initialize tokenizer: {e}")
            self.encoding = None  # type: ignore
        
        self.session_service = get_session_service()
    
    # =========================================================================
    # MAIN BUFFER OPERATIONS
    # =========================================================================
    
    def get_buffer_for_session(self, session_id: str) -> MemoryBuffer:
        """
        Get memory buffer for a session.
        
        Returns:
            MemoryBuffer with recent messages and summary
        """
        try:
            # Get all messages for session
            messages = self.session_service.get_session_messages(session_id)
            
            if not messages:
                return MemoryBuffer(
                    recent_messages=[],
                    summary=None,
                    total_tokens=0,
                    message_count=0
                )
            
            # Split into recent (Tier 1) and older (Tier 2)
            recent_messages = messages[-self.recent_message_count:]
            older_messages = messages[:-self.recent_message_count] if len(messages) > self.recent_message_count else []
            
            # Get or generate summary for older messages
            summary = None
            if older_messages:
                summary = self._get_summary_for_messages(session_id, older_messages)
            
            # Calculate total tokens
            total_tokens = self._calculate_buffer_tokens(recent_messages, summary)
            
            return MemoryBuffer(
                recent_messages=recent_messages,
                summary=summary,
                total_tokens=total_tokens,
                message_count=len(messages)
            )
        except Exception as e:
            logger.error(f"Failed to get buffer for session {session_id}: {e}")
            return MemoryBuffer(
                recent_messages=[],
                summary=None,
                total_tokens=0,
                message_count=0
            )
    
    def format_buffer_for_llm(self, buffer: MemoryBuffer) -> str:
        """
        Format memory buffer for LLM context.
        
        Args:
            buffer: Memory buffer
            
        Returns:
            Formatted context string
        """
        parts = []
        
        # Add summary if exists (Tier 2)
        if buffer.summary:
            parts.append("## Previous Conversation Summary\n")
            parts.append(buffer.summary)
            parts.append("\n\n")
        
        # Add recent messages (Tier 1)
        if buffer.recent_messages:
            parts.append("## Recent Messages\n")
            for msg in buffer.recent_messages:
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                parts.append(f"\n**{role}:**\n{content}\n")
        
        return ''.join(parts)
    
    def should_summarize(self, session_id: str) -> bool:
        """
        Check if session should generate a new summary.
        
        Summarize when:
        - More than 50 messages total
        - More than 10 messages since last summary
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if should summarize
        """
        try:
            messages = self.session_service.get_session_messages(session_id)
            
            # Need at least 50 messages before summarizing
            if len(messages) < 50:
                return False
            
            # Check if we have recent messages that aren't summarized
            older_messages = messages[:-self.recent_message_count]
            return len(older_messages) > 10
        except Exception as e:
            logger.error(f"Failed to check summarization for {session_id}: {e}")
            return False
    
    # =========================================================================
    # TOKEN CALCULATION
    # =========================================================================
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count
            
        Returns:
            Token count
        """
        if not self.encoding:
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4
        
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Failed to count tokens: {e}")
            return len(text) // 4
    
    def _calculate_buffer_tokens(
        self,
        messages: List[Dict[str, Any]],
        summary: Optional[str]
    ) -> int:
        """
        Calculate total tokens in buffer.
        
        Args:
            messages: Recent messages
            summary: Summary text
            
        Returns:
            Total token count
        """
        total = 0
        
        # Count summary tokens
        if summary:
            total += self.count_tokens(summary)
        
        # Count message tokens
        for msg in messages:
            content = msg.get('content', '')
            total += self.count_tokens(content)
        
        return total
    
    # =========================================================================
    # SUMMARIZATION
    # =========================================================================
    
    def _get_summary_for_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Get or generate summary for messages.
        
        For now, returns a simple summary. In production, you'd:
        1. Check if summary exists in database
        2. If not, generate with LLM
        3. Store in database
        
        Args:
            session_id: Session identifier
            messages: Messages to summarize
            
        Returns:
            Summary text or None
        """
        if not messages:
            return None
        
        # For now, create a simple summary
        # TODO: Implement LLM-based summarization
        message_count = len(messages)
        first_msg = messages[0].get('content', '')[:100]
        
        summary = (
            f"This conversation contains {message_count} earlier messages. "
            f"It began with: \"{first_msg}...\" "
            "The conversation covered various topics and interactions."
        )
        
        return summary
    
    def generate_summary(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Generate summary for messages using LLM.
        
        TODO: Implement actual LLM summarization
        
        Args:
            session_id: Session identifier
            messages: Messages to summarize
            
        Returns:
            Summary text or None
        """
        # Placeholder for LLM summarization
        # Would call LLM service to generate concise summary
        return self._get_summary_for_messages(session_id, messages)
    
    # =========================================================================
    # CONTEXT WINDOW MANAGEMENT
    # =========================================================================
    
    def get_available_tokens(self, buffer: MemoryBuffer) -> int:
        """
        Get available tokens for new content.
        
        Args:
            buffer: Current memory buffer
            
        Returns:
            Available token count
        """
        return self.max_tokens - buffer.total_tokens
    
    def is_within_limit(self, buffer: MemoryBuffer) -> bool:
        """
        Check if buffer is within token limit.
        
        Args:
            buffer: Memory buffer
            
        Returns:
            True if within limit
        """
        return buffer.total_tokens <= self.target_tokens
    
    def get_buffer_stats(self, buffer: MemoryBuffer) -> Dict[str, Any]:
        """
        Get buffer statistics.
        
        Args:
            buffer: Memory buffer
            
        Returns:
            Stats dictionary
        """
        return {
            'total_messages': buffer.message_count,
            'recent_messages': len(buffer.recent_messages),
            'has_summary': buffer.summary is not None,
            'total_tokens': buffer.total_tokens,
            'available_tokens': self.get_available_tokens(buffer),
            'utilization': (buffer.total_tokens / self.max_tokens) * 100,
            'within_target': self.is_within_limit(buffer)
        }


# Global instance
_memory_buffer_manager: Optional[MemoryBufferManager] = None


def get_memory_buffer_manager() -> MemoryBufferManager:
    """
    Get or create the global memory buffer manager instance.
    
    Returns:
        MemoryBufferManager instance
    """
    global _memory_buffer_manager
    
    if _memory_buffer_manager is None:
        _memory_buffer_manager = MemoryBufferManager()
    
    return _memory_buffer_manager
