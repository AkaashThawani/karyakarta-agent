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
import json


class SearchInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(description="The search query to look up on Google")
    num_results: Optional[int] = Field(
        default=10,
        description="Number of search results to return (1-20). Default is 10."
    )


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
        return """Search Google for current information on ANY topic.

USE FOR:
- Current events, news, trends (music charts, sports scores, etc.)
- Product information (phones, restaurants, services)
- Location-based queries (dentists, hotels, weather)
- Factual information (definitions, statistics, dates)
- Website discovery (find official sites, reviews, etc.)

EXAMPLES:
- "top 10 songs 2024" → Find music charts
- "best restaurants NYC" → Find dining options  
- "iPhone 15 specs" → Find product details
- "weather San Francisco" → Find weather info

INPUT: Search query string + optional num_results (1-20, default 10)
OUTPUT: Formatted, relevant search results"""
    
    def validate_params(self, **kwargs) -> bool:
        """
        Validate parameters.
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
        if not isinstance(query_value, str) or len(query_value) == 0:
            return False
        
        # Validate num_results if provided
        num_results = kwargs.get("num_results", 10)
        if not isinstance(num_results, int) or num_results < 1 or num_results > 20:
            return False
        
        return True
    
    def _format_search_results(self, raw_results: str, query: str, num_results: int) -> str:
        """
        Format search results and ALWAYS preserve URLs.
        
        Args:
            raw_results: Raw search results from Serper API
            query: Original search query
            num_results: Number of results requested
            
        Returns:
            Formatted results with URLs preserved
        """
        try:
            # ALWAYS try to parse and format JSON to preserve URLs
            if isinstance(raw_results, str) and (raw_results.startswith('{') or raw_results.startswith('[')):
                try:
                    data = json.loads(raw_results)
                    if isinstance(data, dict) and 'organic' in data:
                        results = data['organic'][:num_results]
                        formatted = f"**Search Results for: {query}**\n\n"
                        for i, result in enumerate(results, 1):
                            title = result.get('title', 'No title')
                            snippet = result.get('snippet', 'No description')
                            link = result.get('link', '')  # PRESERVE URL!
                            formatted += f"{i}. **{title}**\n   {snippet}\n   URL: {link}\n\n"
                        
                        print(f"[Search] Formatted {len(results)} results with URLs preserved ({len(formatted)} chars)")
                        return formatted.strip()
                except Exception as e:
                    print(f"[Search] JSON parsing failed: {e}")
            
            # Fallback: return raw (but warn about missing URLs)
            print(f"[Search] Could not parse JSON, returning raw ({len(raw_results)} chars)")
            if len(raw_results) > 2000:
                return raw_results[:2000] + "..."
            
            return raw_results
            
        except Exception as e:
            print(f"[Search] Error: {e}, returning raw")
            return raw_results[:2000] if len(raw_results) > 2000 else raw_results
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute Google search with formatting and compression.
        
        Args:
            **kwargs: May contain 'query', 'num_results'
            
        Returns:
            ToolResult with formatted search results
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        # Get parameters
        query = kwargs.get("query") or kwargs.get("q")
        num_results = kwargs.get("num_results", 10)
        
        # Handle case where query might be passed as the only argument
        if not query and len(kwargs) == 1:
            first_value = next(iter(kwargs.values()))
            if isinstance(first_value, str):
                query = first_value
        
        # Type guards
        if not query or not isinstance(query, str):
            return ToolResult(
                success=False,
                error="Query parameter is required and must be a string",
                metadata=kwargs
            )
        
        if not isinstance(num_results, int):
            num_results = 10
        num_results = max(1, min(20, num_results))  # Clamp 1-20
        
        try:
            if self.logger:
                self.logger.status(f"Searching Google for: {query} (top {num_results} results)")
            
            print(f"\n[SEARCH] Query: {query}")
            print(f"[SEARCH] Num results: {num_results}")
            
            # Execute search - use results() to get raw JSON with URLs
            raw_result = self.search.results(query)
            
            # Convert to string for formatting
            raw_result_str = json.dumps(raw_result) if isinstance(raw_result, dict) else str(raw_result)
            
            print(f"[SEARCH] Raw result length: {len(raw_result_str)} characters")
            
            # Format and compress results (will preserve URLs from JSON)
            formatted_result = self._format_search_results(raw_result_str, query, num_results)
            
            print(f"[SEARCH] Formatted result length: {len(formatted_result)} characters")
            reduction_pct = (1 - len(formatted_result)/len(raw_result_str)) * 100
            print(f"[SEARCH] Size reduction: {reduction_pct:.1f}%")
            
            if self.logger:
                self.logger.status("Google search completed")
            
            return ToolResult(
                success=True,
                data=formatted_result,
                metadata={
                    "query": query,
                    "num_results": num_results,
                    "original_size": len(raw_result),
                    "formatted_size": len(formatted_result)
                }
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
        def google_search(query: str, num_results: int = 10) -> str:
            """Search Google for current information on ANY topic. Works for music, food, healthcare, products, news, anything! Optionally specify num_results (1-20, default 10)."""
            result = tool_instance.execute(query=query, num_results=num_results)
            return tool_instance.format_result(result)
        
        return google_search
