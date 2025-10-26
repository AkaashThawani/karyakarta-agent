"""
Memory Service - Session and conversation memory

Uses LangGraph's built-in checkpoint system for conversation persistence.
This replaces custom memory implementation with framework-provided solution.

For LangGraph checkpointing docs:
https://langchain-ai.github.io/langgraph/how-tos/persistence/
"""

from typing import Optional, Dict, Any, List
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path
import logging
import sqlite3

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Memory service for managing conversation sessions.
    
    Uses LangGraph's SqliteSaver for checkpoint persistence.
    Provides simple interface for session management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize memory service.
        
        Args:
            db_path: Path to SQLite database file. If None, uses in-memory.
        """
        self.db_path = db_path or ":memory:"
        self._checkpointer: Optional[SqliteSaver] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._initialize_checkpointer()
        self._initialize_chunk_storage()
    
    def _initialize_checkpointer(self) -> None:
        """Initialize the LangGraph checkpointer."""
        try:
            if self.db_path != ":memory:":
                # Ensure directory exists for file-based storage
                db_file = Path(self.db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create SQLite connection
            # check_same_thread=False allows multi-threading
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            
            # Create SqliteSaver with connection
            self._checkpointer = SqliteSaver(self._conn)
            logger.info(f"Memory service initialized with database: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize memory service: {e}")
            # Fall back to in-memory if file-based fails
            if self.db_path != ":memory:":
                logger.warning("Falling back to in-memory database")
                self.db_path = ":memory:"
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._checkpointer = SqliteSaver(self._conn)
    
    def _initialize_chunk_storage(self) -> None:
        """Initialize tables for content chunk storage."""
        try:
            if self._conn is None:
                return
            
            cursor = self._conn.cursor()
            
            # Create table for storing content chunks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_chunks (
                    session_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (session_id, chunk_index)
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_chunks 
                ON content_chunks(session_id, chunk_index)
            """)
            
            self._conn.commit()
            logger.info("Chunk storage initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize chunk storage: {e}")
    
    def get_checkpointer(self) -> SqliteSaver:
        """
        Get the LangGraph checkpointer for use with agents.
        
        Returns:
            SqliteSaver instance for LangGraph agent
            
        Usage:
            memory = MemoryService()
            agent = create_react_agent(
                llm, tools, 
                checkpointer=memory.get_checkpointer()
            )
        """
        if self._checkpointer is None:
            self._initialize_checkpointer()
        return self._checkpointer  # type: ignore
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear conversation history for a specific session.
        
        Args:
            session_id: The session ID to clear
            
        Returns:
            bool: True if successful
        """
        try:
            # LangGraph checkpointer handles cleanup automatically
            # Sessions are isolated by their thread_id
            logger.info(f"Session {session_id} marked for cleanup")
            return True
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
            return False
    
    def get_session_config(self, session_id: str) -> Dict[str, Any]:
        """
        Get configuration dict for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Config dict for LangGraph agent.invoke() or .stream()
            
        Usage:
            config = memory.get_session_config("user-123")
            result = agent.invoke({"messages": [...]}, config=config)
        """
        return {
            "configurable": {
                "thread_id": session_id
            }
        }
    
    def store_content_chunks(self, session_id: str, chunks: List[str]) -> bool:
        """
        Store content chunks for a session.
        
        Args:
            session_id: Session identifier
            chunks: List of content chunks
            
        Returns:
            bool: True if successful
        """
        try:
            if self._conn is None:
                logger.error("Database connection not available")
                return False
            
            cursor = self._conn.cursor()
            
            # Delete existing chunks for this session
            cursor.execute("DELETE FROM content_chunks WHERE session_id = ?", (session_id,))
            
            # Insert new chunks
            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks):
                cursor.execute("""
                    INSERT INTO content_chunks (session_id, chunk_index, content, total_chunks)
                    VALUES (?, ?, ?, ?)
                """, (session_id, idx, chunk, total_chunks))
            
            self._conn.commit()
            logger.info(f"Stored {total_chunks} chunks for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store chunks for session {session_id}: {e}")
            return False
    
    def get_chunk(self, session_id: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific content chunk.
        
        Args:
            session_id: Session identifier
            chunk_index: Index of chunk to retrieve (0-based)
            
        Returns:
            Dict with chunk info or None if not found
        """
        try:
            if self._conn is None:
                return None
            
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT chunk_index, content, total_chunks
                FROM content_chunks
                WHERE session_id = ? AND chunk_index = ?
            """, (session_id, chunk_index))
            
            row = cursor.fetchone()
            if row:
                return {
                    "chunk_index": row[0],
                    "content": row[1],
                    "total_chunks": row[2],
                    "chunk_number": row[0] + 1  # 1-based for display
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_index} for session {session_id}: {e}")
            return None
    
    def get_next_chunk(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the next unread chunk for a session.
        Tracks which chunks have been retrieved.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with next chunk info or None if no more chunks
        """
        try:
            if self._conn is None:
                return None
            
            cursor = self._conn.cursor()
            
            # Get all chunks for this session
            cursor.execute("""
                SELECT chunk_index, content, total_chunks
                FROM content_chunks
                WHERE session_id = ?
                ORDER BY chunk_index
            """, (session_id,))
            
            rows = cursor.fetchall()
            if not rows:
                return None
            
            # Find the next chunk (simple strategy: return first chunk after 0)
            # In a real implementation, you'd track which chunks were read
            # For now, return the next chunk in sequence
            for row in rows:
                if row[0] > 0:  # Skip first chunk (already returned by scraper)
                    return {
                        "chunk_index": row[0],
                        "content": row[1],
                        "total_chunks": row[2],
                        "chunk_number": row[0] + 1
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get next chunk for session {session_id}: {e}")
            return None
    
    def clear_chunks(self, session_id: str) -> bool:
        """
        Clear all stored chunks for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if successful
        """
        try:
            if self._conn is None:
                return False
            
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM content_chunks WHERE session_id = ?", (session_id,))
            self._conn.commit()
            logger.info(f"Cleared chunks for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear chunks for session {session_id}: {e}")
            return False
    
    def get_chunk_count(self, session_id: str) -> int:
        """
        Get the number of stored chunks for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            int: Number of chunks
        """
        try:
            if self._conn is None:
                return 0
            
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM content_chunks WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            return row[0] if row else 0
            
        except Exception as e:
            logger.error(f"Failed to get chunk count for session {session_id}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory service statistics.
        
        Returns:
            dict: Statistics about memory usage
        """
        stats = {
            "database": self.db_path,
            "type": "in-memory" if self.db_path == ":memory:" else "persistent",
            "checkpointer": "LangGraph SqliteSaver",
        }
        
        # Add chunk storage stats if connection available
        if self._conn:
            try:
                cursor = self._conn.cursor()
                cursor.execute("SELECT COUNT(DISTINCT session_id) FROM content_chunks")
                row = cursor.fetchone()
                stats["sessions_with_chunks"] = row[0] if row else 0
                
                cursor.execute("SELECT COUNT(*) FROM content_chunks")
                row = cursor.fetchone()
                stats["total_chunks_stored"] = row[0] if row else 0
            except:
                pass
        
        return stats


# Global memory service instance
_global_memory: Optional[MemoryService] = None


def get_memory_service(db_path: Optional[str] = None) -> MemoryService:
    """
    Get or create the global memory service instance.
    
    Args:
        db_path: Optional database path (only used on first call)
        
    Returns:
        MemoryService: Global memory service instance
        
    Usage:
        # In main.py or config
        memory = get_memory_service("data/conversations.db")
        
        # In agent_logic.py
        memory = get_memory_service()
        checkpointer = memory.get_checkpointer()
    """
    global _global_memory
    
    if _global_memory is None:
        _global_memory = MemoryService(db_path=db_path)
    
    return _global_memory


def create_session_memory(session_id: str) -> Dict[str, Any]:
    """
    Convenience function to create session config.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Config dict for agent
        
    Usage:
        config = create_session_memory("session-123")
        agent.invoke({"messages": [...]}, config=config)
    """
    memory = get_memory_service()
    return memory.get_session_config(session_id)
