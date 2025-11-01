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
            # DEBUG: Log parameters being passed
            print(f"[{self.name}] execute() called with parameters: {kwargs}")
            
            # Validate parameters
            if not self.validate_params(**kwargs):
                print(f"[{self.name}] ❌ Parameter validation FAILED!")
                print(f"[{self.name}] ❌ Parameters were: {kwargs}")
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
    
    def _add_completeness_metadata(
        self,
        data: Any,
        requested_count: Optional[int] = None,
        requested_fields: Optional[list] = None,
        task_description: Optional[str] = None,
        truncate_long_text: bool = True,
        max_text_length: int = 500
    ) -> Dict[str, Any]:
        """
        Universal completeness metadata generator for ALL tools.
        
        Validates:
        - Count: Did we get the requested number of items?
        - Fields: Do all items have all required fields?
        - Quality: Are fields non-empty and meaningful?
        - Truncates long text fields (e.g., abstracts > 500 chars)
        
        Args:
            data: The tool's result data (list, dict, str, etc.)
            requested_count: Number of items user requested (e.g., "top 5")
            requested_fields: Fields user requested (e.g., ["title", "abstract"])
            task_description: Original task description for context
            truncate_long_text: Whether to truncate long text fields (default: True)
            max_text_length: Maximum length before truncation (default: 500)
            
        Returns:
            Completeness metadata dict with truncation info
        """
        metadata = {
            "complete": True,
            "requested": {},
            "received": {},
            "coverage": 1.0,
            "reason": "",
            "suggested_action": None,
            "truncated_fields": []
        }
        
        # Determine actual count and fields from data
        actual_count = 0
        actual_fields = []
        missing_fields = []
        truncated_count = 0
        
        # Handle truncation of long text fields in data
        if truncate_long_text and isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, str) and len(value) > max_text_length:
                            # Truncate long text
                            item[key] = value[:300] + "..."
                            truncated_count += 1
                            if key not in metadata["truncated_fields"]:
                                metadata["truncated_fields"].append(key)
        
        if isinstance(data, list) and len(data) > 0:
            actual_count = len(data)
            if isinstance(data[0], dict):
                actual_fields = list(data[0].keys())
        elif isinstance(data, dict):
            actual_count = 1
            actual_fields = list(data.keys())
            # Truncate long text in single dict
            if truncate_long_text:
                for key, value in data.items():
                    if isinstance(value, str) and len(value) > max_text_length:
                        data[key] = value[:300] + "..."
                        truncated_count += 1
                        metadata["truncated_fields"].append(key)
        elif isinstance(data, str):
            # For string results, check if it's structured
            actual_count = 1
        
        # Check count completeness
        if requested_count and actual_count < requested_count:
            metadata["complete"] = False
            metadata["coverage"] = actual_count / requested_count
            metadata["reason"] = f"Got {actual_count}/{requested_count} items"
            metadata["suggested_action"] = "retry_with_pagination"
        
        # Check field completeness
        if requested_fields and actual_fields:
            missing_fields = [f for f in requested_fields if f not in actual_fields]
            if missing_fields:
                metadata["complete"] = False
                metadata["reason"] = f"Missing fields: {', '.join(missing_fields)}"
                metadata["suggested_action"] = "extract_missing_fields"
        
        # Store requested/received info
        metadata["requested"] = {
            "count": requested_count,
            "fields": requested_fields or []
        }
        metadata["received"] = {
            "count": actual_count,
            "fields": actual_fields,
            "missing_fields": missing_fields
        }
        
        # Add truncation info
        if truncated_count > 0:
            metadata["truncated"] = True
            metadata["truncated_count"] = truncated_count
            print(f"[TRUNCATION] Truncated {truncated_count} long text fields: {metadata['truncated_fields']}")
        else:
            metadata["truncated"] = False
        
        return metadata
    
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
