"""
Tool Validator - Pre-execution parameter validation

Validates tool calls before execution to catch parameter errors early.
Provides helpful error messages when validation fails.
"""

from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ToolValidator:
    """
    Validates tool calls before execution.
    
    Checks:
    - Required parameters are present
    - Parameter types match expected types
    - Parameter values are valid
    """
    
    @staticmethod
    def validate_tool_call(
        tool_name: str,
        params: Dict[str, Any],
        tool_schemas: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Validate a tool call against its schema.
        
        Args:
            tool_name: Name of the tool being called
            params: Parameters being passed to the tool
            tool_schemas: Dictionary of tool schemas
            
        Returns:
            Tuple of (is_valid, error_message)
            
        Usage:
            schemas = get_tool_schemas(tools)
            is_valid, error = ToolValidator.validate_tool_call(
                "google_search",
                {"query": "test"},
                schemas
            )
            if not is_valid:
                print(f"Validation failed: {error}")
        """
        # Check if tool exists
        if tool_name not in tool_schemas:
            return False, f"Tool '{tool_name}' not found. Available tools: {', '.join(tool_schemas.keys())}"
        
        schema = tool_schemas[tool_name]
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required parameters
        for param in required:
            if param not in params:
                return False, (
                    f"Missing required parameter: '{param}'. "
                    f"Tool '{tool_name}' requires: {', '.join(required)}"
                )
        
        # Check parameter types
        for param_name, value in params.items():
            if param_name not in properties:
                # Allow extra parameters (some tools are flexible)
                logger.warning(f"Unknown parameter '{param_name}' for tool '{tool_name}'")
                continue
            
            expected_type = properties[param_name].get("type")
            if expected_type:
                is_valid, type_error = ToolValidator._check_type(
                    value, expected_type, param_name
                )
                if not is_valid:
                    return False, type_error
        
        return True, ""
    
    @staticmethod
    def _check_type(value: Any, expected_type: str, param_name: str) -> Tuple[bool, str]:
        """
        Check if value matches expected type.
        
        Args:
            value: The value to check
            expected_type: Expected type string (e.g., "string", "integer")
            param_name: Name of the parameter
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Map Python types to JSON schema types
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array"
        }
        
        actual_type = type(value)
        actual_type_str = type_map.get(actual_type, "unknown")
        
        # Handle number type (int or float)
        if expected_type == "number" and actual_type in (int, float):
            return True, ""
        
        # Handle integer type
        if expected_type == "integer" and actual_type == int:
            return True, ""
        
        # Exact match
        if actual_type_str == expected_type:
            return True, ""
        
        return False, (
            f"Parameter '{param_name}' has incorrect type. "
            f"Expected {expected_type}, got {actual_type_str}. "
            f"Value: {repr(value)[:100]}"
        )
    
    @staticmethod
    def get_tool_schemas(tools: list) -> Dict[str, Dict[str, Any]]:
        """
        Extract schemas from tool list.
        
        Args:
            tools: List of BaseTool instances
            
        Returns:
            Dictionary mapping tool names to their schemas
            
        Usage:
            from src.tools.search import SearchTool
            from src.tools.calculator import CalculatorTool
            
            tools = [SearchTool(), CalculatorTool()]
            schemas = ToolValidator.get_tool_schemas(tools)
        """
        schemas = {}
        
        for tool in tools:
            try:
                # Get LangChain tool
                lc_tool = tool.as_langchain_tool()
                
                # Extract schema if available
                if hasattr(lc_tool, 'args_schema') and lc_tool.args_schema:
                    schema = lc_tool.args_schema.schema()
                    schemas[tool.name] = {
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", []),
                        "description": tool.description
                    }
                else:
                    # Fallback: minimal schema
                    schemas[tool.name] = {
                        "properties": {},
                        "required": [],
                        "description": tool.description
                    }
            except Exception as e:
                logger.error(f"Failed to extract schema for tool '{tool.name}': {e}")
                schemas[tool.name] = {
                    "properties": {},
                    "required": [],
                    "description": tool.description
                }
        
        return schemas
    
    @staticmethod
    def validate_and_suggest(
        tool_name: str,
        params: Dict[str, Any],
        tool_schemas: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and provide suggestions for fixing issues.
        
        Args:
            tool_name: Name of the tool
            params: Parameters being passed
            tool_schemas: Tool schemas
            
        Returns:
            Tuple of (is_valid, error_message, suggestion)
            
        Usage:
            is_valid, error, suggestion = ToolValidator.validate_and_suggest(
                "google_search",
                {"kwargs": "test"},
                schemas
            )
            if not is_valid:
                print(f"Error: {error}")
                print(f"Suggestion: {suggestion}")
        """
        is_valid, error = ToolValidator.validate_tool_call(
            tool_name, params, tool_schemas
        )
        
        if is_valid:
            return True, "", None
        
        # Generate suggestion based on error type
        suggestion = None
        
        if "not found" in error:
            # Tool doesn't exist
            available = list(tool_schemas.keys())
            suggestion = f"Use one of: {', '.join(available)}"
        
        elif "Missing required parameter" in error:
            # Missing parameter
            schema = tool_schemas.get(tool_name, {})
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            
            suggestions = []
            for param in required:
                if param not in params:
                    param_info = properties.get(param, {})
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")
                    suggestions.append(
                        f"Add '{param}' ({param_type}): {param_desc[:100]}"
                    )
            
            suggestion = "\n".join(suggestions)
        
        elif "incorrect type" in error:
            # Type mismatch
            suggestion = "Check the parameter type and convert if necessary"
        
        return False, error, suggestion


# Convenience function for quick validation
def validate_tool_params(
    tool_name: str,
    params: Dict[str, Any],
    tools: list
) -> Tuple[bool, str]:
    """
    Quick validation function.
    
    Args:
        tool_name: Tool to validate
        params: Parameters to check
        tools: List of available tools
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Usage:
        from src.core.validator import validate_tool_params
        
        is_valid, error = validate_tool_params(
            "google_search",
            {"query": "test"},
            [search_tool, calculator_tool]
        )
    """
    schemas = ToolValidator.get_tool_schemas(tools)
    return ToolValidator.validate_tool_call(tool_name, params, schemas)
