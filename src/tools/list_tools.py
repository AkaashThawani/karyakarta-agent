"""
List Tools Meta-Tool - Tool introspection capability

Allows the agent to inspect available tools and their schemas.
This helps the agent understand what tools are available and how to use them.
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


class ListToolsTool(BaseTool):
    """
    Meta-tool that lists all available tools and their schemas.
    
    This enables tool introspection - the agent can query what tools
    are available and how to use them before making a tool call.
    """
    
    def __init__(self, tools: List[BaseTool], logger=None):
        """
        Initialize with list of available tools.
        
        Args:
            tools: List of tool instances
            logger: Optional logging service
        """
        super().__init__(logger)
        self.tools = tools
    
    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "list_available_tools"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """List all available tools with their parameters and usage information.

        Use this tool when you:
        - Are unsure which tool to use for a task
        - Need to check the exact parameters a tool accepts
        - Want to verify a tool exists before calling it
        - Need to understand what each tool does
        
        This tool takes no parameters and returns detailed information about
        all available tools including their names, descriptions, parameters,
        and usage examples.
        
        Example: list_available_tools()
        """
    
    def validate_params(self, **kwargs) -> bool:
        """This tool takes no parameters."""
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        List all available tools with their schemas.
        
        Returns:
            ToolResult with formatted tool information
        """
        if self.logger:
            self.logger.status("Listing available tools...")
        
        tools_info = []
        
        for tool in self.tools:
            # Get tool schema if available
            tool_data = {
                "name": tool.name,
                "description": tool.description,
            }
            
            # Try to get parameter schema from LangChain tool
            lc_tool = tool.as_langchain_tool()
            if hasattr(lc_tool, 'args_schema') and lc_tool.args_schema:
                schema = lc_tool.args_schema.schema()
                tool_data["parameters"] = schema.get("properties", {})
                tool_data["required"] = schema.get("required", [])
            
            tools_info.append(tool_data)
        
        # Format output
        output = ["Available Tools:", "=" * 50, ""]
        
        for i, info in enumerate(tools_info, 1):
            output.append(f"{i}. {info['name']}")
            output.append(f"   Description: {info['description'][:200]}...")
            
            if "parameters" in info:
                output.append("   Parameters:")
                for param_name, param_info in info["parameters"].items():
                    required = " (required)" if param_name in info.get("required", []) else " (optional)"
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")
                    output.append(f"     - {param_name}{required}: {param_type}")
                    if param_desc:
                        output.append(f"       {param_desc[:150]}")
            
            output.append("")
        
        result = "\n".join(output)
        
        if self.logger:
            self.logger.status(f"Listed {len(tools_info)} available tools")
        
        return ToolResult(
            success=True,
            data=result,
            metadata={"tool_count": len(tools_info)}
        )
    
    def as_langchain_tool(self):
        """
        Convert to LangChain tool.
        
        Returns:
            LangChain tool
        """
        tool_instance = self
        
        @tool
        def list_available_tools() -> str:
            """List all available tools with their parameters and usage information. Use this when unsure which tool to use or how to call it."""
            result = tool_instance.execute()
            return tool_instance.format_result(result)
        
        return list_available_tools
