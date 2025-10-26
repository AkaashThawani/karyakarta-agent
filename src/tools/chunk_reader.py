"""
Chunk Reader Tool - Read next chunk of content

Allows the agent to request the next chunk of content when
large content was split during scraping.
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from src.core.memory import get_memory_service


class ChunkReaderInput(BaseModel):
    """Input schema for chunk reader tool - no parameters needed."""
    pass


class GetNextChunkTool(BaseTool):
    """
    Tool for reading the next chunk of scraped content.
    
    When the scraper splits content into multiple chunks,
    the agent can use this tool to read subsequent chunks.
    """
    
    def __init__(self, session_id: str, logger: Optional[LoggingService] = None):
        """
        Initialize chunk reader tool.
        
        Args:
            session_id: Current session ID
            logger: Optional logging service
        """
        super().__init__(logger)
        self.session_id = session_id
        self.memory_service = get_memory_service()
    
    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "get_next_chunk"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """Use this tool to read the next chunk of content from a previously scraped website.
        
        Use this when:
        - A previous browse_website call indicated content was split into chunks
        - You need more information from the scraped content
        - The message said "Content split into N chunks. Use get_next_chunk() to read more"
        
        This tool requires no parameters.
        
        Example: get_next_chunk()
        """
    
    def validate_params(self, **kwargs) -> bool:
        """No parameters needed - always valid."""
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Read the next chunk of content.
        
        Returns:
            ToolResult with next chunk or message if no more chunks
        """
        print(f"\n{'='*70}")
        print(f"📖 GET NEXT CHUNK - Session: {self.session_id}")
        print(f"{'='*70}")
        
        if self.logger:
            self.logger.status("Retrieving next content chunk...")
        
        try:
            # Get next chunk from memory
            chunk_data = self.memory_service.get_next_chunk(self.session_id)
            
            if chunk_data is None:
                message = "No more content chunks available."
                print(f"[CHUNK READER] ℹ️ {message}")
                print(f"{'='*70}\n")
                
                if self.logger:
                    self.logger.status(message)
                
                return ToolResult(
                    success=True,
                    data=message,
                    metadata={"has_more": False}
                )
            
            # Return the chunk
            chunk_num = chunk_data["chunk_number"]
            total = chunk_data["total_chunks"]
            content = chunk_data["content"]
            
            message = f"Chunk {chunk_num} of {total}:\n\n{content}"
            
            print(f"[CHUNK READER] ✅ Returning chunk {chunk_num} of {total}")
            print(f"[CHUNK READER] Content length: {len(content)} characters")
            print(f"{'='*70}\n")
            
            if self.logger:
                self.logger.status(f"Retrieved chunk {chunk_num} of {total}")
            
            has_more = chunk_num < total
            
            return ToolResult(
                success=True,
                data=message,
                metadata={
                    "chunk_number": chunk_num,
                    "total_chunks": total,
                    "has_more": has_more
                }
            )
            
        except Exception as e:
            error_msg = f"Error retrieving next chunk: {str(e)}"
            print(f"[CHUNK READER] ❌ {error_msg}")
            print(f"{'='*70}\n")
            
            if self.logger:
                self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={}
            )
    
    def as_langchain_tool(self):
        """Convert to LangChain tool with proper schema."""
        tool_instance = self
        
        @tool
        def get_next_chunk() -> str:
            """Use this tool to read the next chunk of content from a previously scraped website. No parameters needed."""
            result = tool_instance.execute()
            return tool_instance.format_result(result)
        
        return get_next_chunk
