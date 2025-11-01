"""
Data Flow Resolver - Automatic input resolution using tool I/O schemas

This module provides ZERO-hardcoding data flow resolution between tools.
All mappings are defined declaratively in tool_io_schema.json.

Usage:
    from src.core.data_flow_resolver import DataFlowResolver
    
    resolver = DataFlowResolver()
    
    # Resolve inputs automatically
    resolved_params = resolver.resolve_inputs(
        tool_name="chart_extractor",
        provided_params={"required_fields": ["title", "url"]},
        accumulated_data=accumulated_data
    )
    # Automatically adds "url" from google_search.urls[0]
    
    # Extract outputs automatically
    extracted = resolver.extract_outputs(
        tool_name="google_search",
        raw_result="Search results with https://example.com..."
    )
    # Returns: {"text": "...", "urls": ["https://example.com"], "snippets": [...]}
"""

import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.core.data_extractors import get_extractor


class DataFlowResolver:
    """
    Generic data flow resolver using tool I/O schemas.
    Automatically maps tool outputs → tool inputs with ZERO hardcoding.
    """
    
    def __init__(self, schema_file: str = "tool_io_schema.json"):
        """
        Initialize resolver with tool I/O schemas.
        
        Args:
            schema_file: Path to schema file (relative to project root)
        """
        # Find schema file (it's in project root)
        schema_path = Path(__file__).parent.parent.parent / schema_file
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        # Load schemas
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.tool_schemas = json.load(f)
        
        # Remove non-tool keys like $schema, title, etc.
        schema_metadata = ['$schema', 'title', 'description', 'version']
        for key in schema_metadata:
            self.tool_schemas.pop(key, None)
        
        print(f"[DataFlowResolver] Loaded {len(self.tool_schemas)} tool schemas from {schema_file}")
    
    def resolve_inputs(
        self,
        tool_name: str,
        provided_params: Dict[str, Any],
        accumulated_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Automatically resolve missing required inputs.
        
        This method looks at the tool's input schema, identifies required
        inputs that are missing from provided_params, and attempts to resolve
        them from previous tool outputs in accumulated_data.
        
        Args:
            tool_name: Name of tool to execute
            provided_params: Parameters explicitly provided
            accumulated_data: Previous tool results with extracted data
            
        Returns:
            Complete parameters with resolved inputs
        """
        # Check if tool exists in schema
        if tool_name not in self.tool_schemas:
            print(f"[DataFlowResolver] No schema for {tool_name}, returning params as-is")
            return provided_params
        
        tool_schema = self.tool_schemas[tool_name]
        resolved_params = provided_params.copy()
        
        # Get input specifications
        inputs = tool_schema.get("inputs", {})
        
        if not inputs:
            return resolved_params
        
        # For each input specification
        for input_name, input_spec in inputs.items():
            # Check if parameter is provided but contains a placeholder
            if input_name in resolved_params:
                param_value = resolved_params[input_name]
                
                # Detect template syntax placeholders like "{{variable.field}}"
                if isinstance(param_value, str) and "{{" in param_value and "}}" in param_value:
                    print(f"[DataFlowResolver] Detected template placeholder: {param_value}")
                    
                    # Try to resolve template
                    resolved_value = self._resolve_template(param_value, accumulated_data)
                    
                    if resolved_value is not None:
                        resolved_params[input_name] = resolved_value
                        print(f"[DataFlowResolver] ✓ Resolved template {tool_name}.{input_name}: '{param_value}' → '{resolved_value}'")
                    else:
                        print(f"[DataFlowResolver] ⚠️ Could not resolve template: {param_value}")
                
                # Detect old-style placeholders like "PREVIOUS_STEP_RESULT.field"
                elif isinstance(param_value, str) and param_value.startswith("PREVIOUS_STEP_RESULT."):
                    placeholder = param_value.replace("PREVIOUS_STEP_RESULT.", "")
                    print(f"[DataFlowResolver] Detected placeholder: {param_value}")
                    
                    # Try to resolve from accumulated data
                    resolved_value = self._resolve_placeholder(placeholder, accumulated_data)
                    
                    if resolved_value is not None:
                        resolved_params[input_name] = resolved_value
                        print(f"[DataFlowResolver] ✓ Resolved placeholder {tool_name}.{input_name}: '{param_value}' → '{resolved_value}'")
                    else:
                        print(f"[DataFlowResolver] ⚠️ Could not resolve placeholder: {param_value}")
                
                # Already has a value (and not a placeholder), skip
                continue
            
            # Check if this input can accept data from previous tools
            accepts_from = input_spec.get("accepts_from", [])
            
            if not accepts_from:
                # No automatic resolution available
                continue
            
            # Try each source path in order
            for source_path in accepts_from:
                value = self._extract_from_source(source_path, accumulated_data)
                
                if value is not None:
                    resolved_params[input_name] = value
                    print(f"[DataFlowResolver] ✓ Resolved {tool_name}.{input_name} ← {source_path}")
                    break  # Found a value, stop trying other sources
            
            # If still not resolved and required, log warning
            if input_name not in resolved_params and input_spec.get("required", False):
                print(f"[DataFlowResolver] ⚠ Required input '{input_name}' for {tool_name} could not be resolved")
        
        return resolved_params
    
    def _resolve_template(
        self,
        template: str,
        accumulated_data: Dict[str, Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Resolve a template like "{{variable.field}}" or "{{variable.field[0]}}" from accumulated data.
        
        Supports:
        - {{variable.field}} - Simple field access
        - {{variable.field[0]}} - Array indexing
        - {{variable.nested.field}} - Nested field access
        
        Args:
            template: Template string with {{...}} placeholder
            accumulated_data: Dict of previous tool results
            
        Returns:
            Resolved value or None if not found
        """
        # Extract content between {{ and }}
        match = re.search(r'\{\{(.+?)\}\}', template)
        if not match:
            print(f"[DataFlowResolver] Invalid template format: {template}")
            return None
        
        expression = match.group(1).strip()
        print(f"[DataFlowResolver] Parsing template expression: {expression}")
        
        # Parse expression: "variable.field[index]" or "variable.field.subfield"
        # Split by dots, but preserve array indices
        parts = []
        current = ""
        in_brackets = False
        
        for char in expression:
            if char == '[':
                in_brackets = True
                current += char
            elif char == ']':
                in_brackets = False
                current += char
            elif char == '.' and not in_brackets:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        print(f"[DataFlowResolver] Expression parts: {parts}")
        
        if not parts:
            return None
        
        # First part is the variable/step name
        variable_name = parts[0]
        
        # Find matching step in accumulated data
        step_data = None
        for step_name in accumulated_data.keys():
            # Match if variable name is contained in step name
            if variable_name.lower() in step_name.lower():
                step_data = accumulated_data[step_name]
                print(f"[DataFlowResolver] Found matching step: {step_name}")
                break
        
        if not step_data:
            print(f"[DataFlowResolver] No step found for variable: {variable_name}")
            return None
        
        # Navigate through the remaining parts
        value = step_data.get("extracted", {})
        
        for i, part in enumerate(parts[1:], 1):
            # Check for array indexing: "field[0]"
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            
            if array_match:
                field_name, index = array_match.groups()
                print(f"[DataFlowResolver] Accessing {field_name}[{index}]")
                
                # Get the field
                if isinstance(value, dict):
                    value = value.get(field_name)
                else:
                    print(f"[DataFlowResolver] Cannot access field on non-dict: {type(value)}")
                    return None
                
                # Index into array
                if isinstance(value, list):
                    idx = int(index)
                    if 0 <= idx < len(value):
                        value = value[idx]
                    else:
                        print(f"[DataFlowResolver] Index {idx} out of range (len={len(value)})")
                        return None
                else:
                    print(f"[DataFlowResolver] Cannot index non-list: {type(value)}")
                    return None
            else:
                # Simple field access
                print(f"[DataFlowResolver] Accessing field: {part}")
                
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    print(f"[DataFlowResolver] Cannot access field on non-dict: {type(value)}")
                    return None
            
            if value is None:
                print(f"[DataFlowResolver] Field not found: {part}")
                return None
        
        print(f"[DataFlowResolver] Successfully resolved to: {value}")
        return value
    
    def _resolve_placeholder(
        self,
        placeholder: str,
        accumulated_data: Dict[str, Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Resolve a placeholder like "url" or "urls[0]" from accumulated data.
        
        Searches through all previous tool results to find the field.
        
        Args:
            placeholder: Field name with optional array index (e.g., "url", "urls[0]")
            accumulated_data: Dict of previous tool results
            
        Returns:
            Resolved value or None if not found
        """
        # Parse placeholder: "field" or "field[index]"
        match = re.match(r'(\w+)(?:\[(\d+)\])?', placeholder)
        if not match:
            print(f"[DataFlowResolver] Invalid placeholder format: {placeholder}")
            return None
        
        field_name, index = match.groups()
        
        # Search through all previous steps (in reverse order for most recent)
        for step_name in reversed(list(accumulated_data.keys())):
            step_data = accumulated_data[step_name]
            
            # Try extracted outputs first
            extracted = step_data.get("extracted", {})
            value = extracted.get(field_name)
            
            if value is None:
                # Try raw result as fallback
                raw_result = step_data.get("result", {})
                if isinstance(raw_result, dict):
                    result_data = raw_result.get("data")
                    if isinstance(result_data, dict):
                        value = result_data.get(field_name)
            
            if value is None:
                continue
            
            # Handle array indexing
            if index is not None:
                if isinstance(value, list):
                    idx = int(index)
                    if 0 <= idx < len(value):
                        return value[idx]
                    else:
                        print(f"[DataFlowResolver] Index {idx} out of range for {field_name}")
                        return None
                else:
                    print(f"[DataFlowResolver] Cannot index non-list value for {field_name}")
                    return None
            
            return value
        
        # Not found in any step
        print(f"[DataFlowResolver] Field '{field_name}' not found in accumulated data")
        return None
    
    def _extract_from_source(
        self,
        source_path: str,
        accumulated_data: Dict[str, Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Extract value from source path like "google_search.urls[0]".
        
        Source path format: "tool_name.output_field[index]"
        - tool_name: Name of previous tool
        - output_field: Name of output field from that tool
        - [index]: Optional array index (e.g., [0] for first item)
        
        Args:
            source_path: Path specification
            accumulated_data: Dict of previous tool results
            
        Returns:
            Extracted value or None if not found
        """
        # Parse source path: "tool_name.field[index]"
        match = re.match(r'(\w+)\.(\w+)(?:\[(\d+)\])?', source_path)
        if not match:
            print(f"[DataFlowResolver] Invalid source path format: {source_path}")
            return None
        
        tool_name, field, index = match.groups()
        
        # Find matching tool result in accumulated_data
        # accumulated_data keys are like "step_0_google_search", "step_1_chart_extractor"
        for step_name, step_data in accumulated_data.items():
            if tool_name not in step_name:
                continue
            
            # Get extracted data (structured outputs)
            extracted = step_data.get("extracted", {})
            value = extracted.get(field)
            
            if value is None:
                # Try raw result as fallback
                raw_result = step_data.get("result", {})
                if isinstance(raw_result, dict):
                    value = raw_result.get("data", {}).get(field)
            
            if value is None:
                continue
            
            # Handle array indexing
            if index is not None:
                if isinstance(value, list):
                    idx = int(index)
                    if 0 <= idx < len(value):
                        return value[idx]
                    else:
                        print(f"[DataFlowResolver] Index {idx} out of range for {source_path}")
                        return None
                else:
                    print(f"[DataFlowResolver] Cannot index non-list value for {source_path}")
                    return None
            
            return value
        
        # Not found in any step
        return None
    
    def extract_outputs(
        self,
        tool_name: str,
        raw_result: Any
    ) -> Dict[str, Any]:
        """
        Extract structured outputs with DYNAMIC field support.
        
        Extracts both schema-defined fields AND preserves dynamic fields.
        Ensures zero data loss while providing structured access.
        
        Args:
            tool_name: Name of tool that produced the result
            raw_result: Raw result data from tool
            
        Returns:
            Dict of extracted outputs (schema-defined + dynamic + raw)
        """
        if tool_name not in self.tool_schemas:
            print(f"[DataFlowResolver] No schema for {tool_name}, preserving raw data")
            # No schema, but still preserve data
            return {"_raw": raw_result}
        
        tool_schema = self.tool_schemas[tool_name]
        outputs = tool_schema.get("outputs", {})
        metadata = tool_schema.get("metadata", {})
        
        extracted = {}
        
        # Extract schema-defined outputs
        for output_name, output_spec in outputs.items():
            if output_name == "*":
                continue  # Handle wildcard separately
            
            extractor_name = output_spec.get("extractor", "identity")
            extractor_func = get_extractor(extractor_name)
            
            try:
                # Apply extractor to raw result
                extracted[output_name] = extractor_func(raw_result)
            except Exception as e:
                print(f"[DataFlowResolver] Extraction failed for {tool_name}.{output_name}: {e}")
                extracted[output_name] = None
        
        # DYNAMIC FIELD SUPPORT
        supports_dynamic = metadata.get("supports_dynamic_outputs", True)  # Default: True!
        
        if supports_dynamic:
            # Pass through dynamic fields from raw result
            if isinstance(raw_result, dict):
                # Add any fields not already extracted
                for key, value in raw_result.items():
                    if key not in extracted and not key.startswith("_"):
                        extracted[key] = value
                        print(f"[DataFlowResolver] Dynamic field: {tool_name}.{key}")
            
            elif isinstance(raw_result, list) and raw_result:
                # For list results, preserve full records
                if isinstance(raw_result[0], dict):
                    # Extract all field names from first record
                    all_fields = list(raw_result[0].keys())
                    extracted["_all_fields"] = all_fields
                    extracted["_records"] = raw_result
                    print(f"[DataFlowResolver] Dynamic list: {len(all_fields)} fields, {len(raw_result)} records")
        
        # ALWAYS preserve raw data reference
        extracted["_raw"] = raw_result
        
        print(f"[DataFlowResolver] Extracted {len(extracted)} outputs for {tool_name} (dynamic={supports_dynamic})")
        
        return extracted
    
    def validate_inputs(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Validate that all required inputs are present.
        
        Args:
            tool_name: Name of tool
            params: Parameters to validate
            
        Returns:
            Tuple of (is_valid, missing_required_fields)
        """
        if tool_name not in self.tool_schemas:
            return True, []
        
        tool_schema = self.tool_schemas[tool_name]
        inputs = tool_schema.get("inputs", {})
        
        missing = []
        for input_name, input_spec in inputs.items():
            if input_spec.get("required", False) and input_name not in params:
                missing.append(input_name)
        
        return len(missing) == 0, missing
    
    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a tool.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Metadata dict or None
        """
        if tool_name not in self.tool_schemas:
            return None
        
        return self.tool_schemas[tool_name].get("metadata", {})
    
    def list_tools(self) -> List[str]:
        """
        List all tool names in the schema.
        
        Returns:
            List of tool names
        """
        return list(self.tool_schemas.keys())
    
    def get_tool_inputs(self, tool_name: str) -> Dict[str, Any]:
        """
        Get input specifications for a tool.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Dict of input specifications
        """
        if tool_name not in self.tool_schemas:
            return {}
        
        return self.tool_schemas[tool_name].get("inputs", {})
    
    def get_tool_outputs(self, tool_name: str) -> Dict[str, Any]:
        """
        Get output specifications for a tool.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Dict of output specifications
        """
        if tool_name not in self.tool_schemas:
            return {}
        
        return self.tool_schemas[tool_name].get("outputs", {})
    
    def get_schema_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the loaded schemas.
        
        Returns:
            Dict with schema statistics
        """
        total_inputs = 0
        total_outputs = 0
        tools_by_category = {}
        
        for tool_name, tool_schema in self.tool_schemas.items():
            # Count inputs/outputs
            inputs = tool_schema.get("inputs", {})
            outputs = tool_schema.get("outputs", {})
            total_inputs += len(inputs)
            total_outputs += len(outputs)
            
            # Group by category
            category = tool_schema.get("metadata", {}).get("category", "uncategorized")
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool_name)
        
        return {
            "total_tools": len(self.tool_schemas),
            "total_inputs": total_inputs,
            "total_outputs": total_outputs,
            "tools_by_category": tools_by_category
        }


# Singleton instance
_resolver_instance: Optional[DataFlowResolver] = None


def get_resolver() -> DataFlowResolver:
    """
    Get the singleton DataFlowResolver instance.
    
    Returns:
        DataFlowResolver instance
    """
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = DataFlowResolver()
    return _resolver_instance
