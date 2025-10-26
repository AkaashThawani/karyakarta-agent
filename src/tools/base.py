"""
Base Tool Class - PRIORITY 2

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Abstract base class that all tools must inherit from.
Enforces consistent interface following SOLID principles.

Usage:
    from src.tools.base import BaseTool, ToolResult
    from langchain_core.tools import tool
    
    class MyTool(BaseTool):
        @property
        def name(self) -> str:
            return "my_tool"
        
        @property
        def description(self) -> str:
            return "Description of what the tool does"
        
        def _execute_impl(self, **kwargs) -> ToolResult:
            # Implementation
            return ToolResult(success=True, data=result)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from pydantic import BaseModel, Field
from langchain_core.tools import tool as langchain_tool
from src.services.logging_service import LoggingService


class ToolResult(BaseModel):
    """Standardized result from tool execution."""
    success: bool = Field(..., description="Whether the tool execution succeeded")
    data: Any = Field(default=None, description="The result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": "Search results here",
                "error": None,
                "metadata": {"query": "test search"}
            }
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    All tools must implement:
    - name: Tool identifier for LangChain
    - description: What the tool does (for LLM to understand)
    - _execute_impl: The actual tool logic
    """
    
    def __init__(self, logger: Optional[LoggingService] = None):
        """
        Initialize the tool.
        
        Args:
            logger: Optional logging service for tool execution logs
        """
        self.logger = logger
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for LangChain registration."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM to understand when to use it."""
        pass
    
    @abstractmethod
    def _execute_impl(self, *args, **kwargs) -> ToolResult:
        """
        Execute the tool logic.
        
        Subclasses can define specific parameters (e.g., query: str, url: str)
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            ToolResult with success status and data or error
        """
        pass
    
    def execute(self, **kwargs) -> ToolResult:
        """
        Public execute method with error handling.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with success status and data or error
        """
        try:
            # Validate parameters
            if not self.validate_params(**kwargs):
                return ToolResult(
                    success=False,
                    error="Invalid parameters provided",
                    metadata=kwargs
                )
            
            # Execute the tool
            result = self._execute_impl(**kwargs)
            return result
            
        except Exception as e:
            error_msg = f"Error executing {self.name}: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata=kwargs
            )
    
    def validate_params(self, **kwargs) -> bool:
        """
        Validate input parameters.
        Override in subclass for custom validation.
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return True
    
    def format_result(self, result: ToolResult) -> str:
        """
        Format result for LLM consumption.
        Override in subclass for custom formatting.
        
        Args:
            result: The ToolResult to format
            
        Returns:
            str: Formatted result string
        """
        if result.success:
            return str(result.data)
        else:
            return f"Error: {result.error}"
    
    def as_langchain_tool(self) -> Any:
        """
        Convert this tool to a LangChain tool.
        
        Returns:
            A LangChain tool function that can be used with LangGraph
        """
        tool_name = self.name
        tool_desc = self.description
        tool_instance = self
        
        def tool_function(**kwargs) -> str:
            """Dynamically created LangChain tool."""
            result = tool_instance.execute(**kwargs)
            return tool_instance.format_result(result)
        
        # Apply the decorator manually with name and description
        tool_function.__name__ = tool_name
        tool_function.__doc__ = tool_desc
        
        return langchain_tool(tool_function)
