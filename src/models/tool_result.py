"""
Tool Result Model

Standardized result model for all tool executions.
Provides consistent interface for tool outputs with success/error handling.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ToolResult(BaseModel):
    """
    Standardized result from tool execution.
    
    All tools return this consistent format to enable:
    - Uniform error handling
    - Result validation
    - Metadata tracking
    - Success/failure detection
    
    Example:
        # Success case
        result = ToolResult(
            success=True,
            data={"results": [...]},
            metadata={"source": "google", "count": 10}
        )
        
        # Error case
        result = ToolResult(
            success=False,
            data=None,
            error="API rate limit exceeded",
            metadata={"retry_after": 60}
        )
    """
    
    success: bool = Field(
        description="Whether the tool execution succeeded"
    )
    
    data: Optional[Any] = Field(
        default=None,
        description="Tool output data (any type: str, dict, list, etc.)"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution"
    )
    
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp of the result"
    )
    
    tool_name: Optional[str] = Field(
        default=None,
        description="Name of the tool that produced this result"
    )
    
    def __str__(self) -> str:
        """String representation for logging."""
        if self.success:
            return f"ToolResult(success=True, tool={self.tool_name})"
        else:
            return f"ToolResult(success=False, error='{self.error}')"
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"result": "example data"},
                "error": None,
                "metadata": {"execution_time": 0.5},
                "timestamp": "2025-10-25T10:30:00",
                "tool_name": "search_tool"
            }
        }
