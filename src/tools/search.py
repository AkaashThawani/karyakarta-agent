"""
Search Tools - PRIORITY 2

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Google search tool using Serper API.
Refactored from google_search() function to use BaseTool interface.

Usage:
    from src.tools.search import SearchTool
    from src.services.logging_service import LoggingService
    from src.core.config import settings
    
    logger = LoggingService(settings.logging_url)
    search_tool = SearchTool(logger)
    
    # Use as LangChain tool
    tool = search_tool.as_langchain_tool()
"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


class SearchInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(description="The search query to look up on Google")


class SearchTool(BaseTool):
    """
    Google search tool using Serper API.
    Searches the web for current information.
    """
    
    def __init__(self, logger: Optional[LoggingService] = None):
        """
        Initialize the search tool.
        
        Args:
            logger: Optional logging service
        """
        super().__init__(logger)
        self.search = GoogleSerperAPIWrapper()
    
    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "google_search"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return "Use this tool to search Google for recent information or to find websites. Input should be a search query string."
    
    def validate_params(self, **kwargs) -> bool:
        """
        Validate that query parameter is provided.
        Accepts both 'query' and 'q' parameter names for flexibility.
        Handles nested kwargs from LangChain.
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        # Accept both 'query' and 'q' parameter names
        has_query = "query" in kwargs or "q" in kwargs
        if not has_query:
            return False
        
        query_value = kwargs.get("query") or kwargs.get("q")
        return isinstance(query_value, str) and len(query_value) > 0
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute Google search with flexible parameter handling.
        
        Args:
            **kwargs: May contain 'query' or 'q' parameter, possibly nested in 'kwargs'
            
        Returns:
            ToolResult with search results or error
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        # Get query parameter  
        query = kwargs.get("query") or kwargs.get("q")
        
        # Handle case where query might be passed as the only argument
        if not query and len(kwargs) == 1:
            # If there's only one argument and it's a string, use it as the query
            first_value = next(iter(kwargs.values()))
            if isinstance(first_value, str):
                query = first_value
        
        # Type guard - should not happen due to validate_params, but needed for type checker
        if not query or not isinstance(query, str):
            return ToolResult(
                success=False,
                error="Query parameter is required and must be a string",
                metadata=kwargs
            )
        
        try:
            if self.logger:
                self.logger.status(f"Searching Google for: {query}")
            
            # Execute search
            result = self.search.run(query)
            
            if self.logger:
                self.logger.status("Google search completed")
            
            return ToolResult(
                success=True,
                data=result,
                metadata={"query": query}
            )
            
        except Exception as e:
            error_msg = f"Google search failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"query": query}
            )
    
    def as_langchain_tool(self):
        """
        Convert to LangChain tool with proper schema.
        
        Returns:
            LangChain tool with input schema
        """
        tool_instance = self
        
        @tool(args_schema=SearchInput)
        def google_search(query: str) -> str:
            """Use this tool to search Google for recent information or to find websites. Input should be a search query string."""
            result = tool_instance.execute(query=query)
            return tool_instance.format_result(result)
        
        return google_search
