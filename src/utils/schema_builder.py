"""
Schema Builder - Automatic JSON Schema Generation

Builds JSON schemas from extracted data automatically.
Zero hardcoding - adapts to any data structure.
"""

from typing import List, Dict, Any, Optional, Set
import json


class SchemaBuilder:
    """
    Automatically builds JSON schemas from data records.
    
    Features:
    - Type inference from values
    - Example collection
    - Required field detection
    - Nested object support
    """
    
    def __init__(self):
        """Initialize Schema Builder."""
        self.schemas = {}  # Cache schemas by category
    
    def build_schema(
        self,
        records: List[Dict[str, Any]],
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build JSON schema from records.
        
        Args:
            records: List of data records
            category: Optional category name for caching
            
        Returns:
            JSON Schema dict
        """
        if not records:
            return {
                "type": "object",
                "properties": {},
                "required": []
            }
        
        # Check cache
        if category and category in self.schemas:
            return self.schemas[category]
        
        # Analyze sample records
        sample_size = min(10, len(records))
        sample = records[:sample_size]
        
        # Build schema
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Track field presence
        field_counts = {}
        
        # Analyze each record
        for record in sample:
            for key, value in record.items():
                # Count field presence
                field_counts[key] = field_counts.get(key, 0) + 1
                
                # Add property if new
                if key not in schema["items"]["properties"]:
                    schema["items"]["properties"][key] = self._build_property_schema(key, value)
                    
                    # Add examples
                    schema["items"]["properties"][key]["examples"] = []
                
                # Collect examples (up to 3)
                examples = schema["items"]["properties"][key]["examples"]
                if len(examples) < 3 and value not in examples:
                    examples.append(value)
        
        # Mark required fields (present in >80% of records)
        threshold = sample_size * 0.8
        for field, count in field_counts.items():
            if count >= threshold:
                schema["items"]["required"].append(field)
        
        # Cache if category provided
        if category:
            self.schemas[category] = schema
        
        return schema
    
    def _build_property_schema(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Build schema for a single property.
        
        Args:
            key: Property name
            value: Sample value
            
        Returns:
            Property schema
        """
        prop_schema = {
            "type": self._infer_type(value),
            "description": self._generate_description(key)
        }
        
        # Add format hints for common patterns
        if prop_schema["type"] == "string":
            if "price" in key.lower() or "cost" in key.lower():
                prop_schema["format"] = "currency"
            elif "date" in key.lower() or "time" in key.lower():
                prop_schema["format"] = "date-time"
            elif "email" in key.lower():
                prop_schema["format"] = "email"
            elif "url" in key.lower() or "link" in key.lower():
                prop_schema["format"] = "uri"
        
        # Add constraints for numbers
        elif prop_schema["type"] in ["integer", "number"]:
            if "rating" in key.lower() or "score" in key.lower():
                prop_schema["minimum"] = 0
                prop_schema["maximum"] = 10
            elif "price" in key.lower():
                prop_schema["minimum"] = 0
        
        return prop_schema
    
    def _infer_type(self, value: Any) -> str:
        """
        Infer JSON Schema type from value.
        
        Args:
            value: Sample value
            
        Returns:
            JSON Schema type string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"
    
    def _generate_description(self, key: str) -> str:
        """
        Generate human-readable description from field name.
        
        Args:
            key: Field name
            
        Returns:
            Description string
        """
        # Convert snake_case or camelCase to words
        import re
        
        # Handle camelCase
        words = re.sub('([A-Z])', r' \1', key)
        
        # Handle snake_case
        words = words.replace('_', ' ')
        
        # Capitalize first letter
        description = words.strip().capitalize()
        
        return description
    
    def validate_record(
        self,
        record: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a record against schema.
        
        Args:
            record: Data record
            schema: JSON Schema
            
        Returns:
            Validation result with errors/warnings
        """
        errors = []
        warnings = []
        
        item_schema = schema.get("items", {})
        properties = item_schema.get("properties", {})
        required = item_schema.get("required", [])
        
        # Check required fields
        for field in required:
            if field not in record or record[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        for field, value in record.items():
            if field in properties:
                expected_type = properties[field].get("type")
                actual_type = self._infer_type(value)
                
                if actual_type != expected_type:
                    warnings.append(
                        f"Field '{field}' has type '{actual_type}', "
                        f"expected '{expected_type}'"
                    )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def merge_schemas(
        self,
        schema1: Dict[str, Any],
        schema2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two schemas into one.
        
        Args:
            schema1: First schema
            schema2: Second schema
            
        Returns:
            Merged schema
        """
        merged = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Merge properties
        props1 = schema1.get("items", {}).get("properties", {})
        props2 = schema2.get("items", {}).get("properties", {})
        
        all_fields = set(props1.keys()) | set(props2.keys())
        
        for field in all_fields:
            if field in props1:
                merged["items"]["properties"][field] = props1[field]
            else:
                merged["items"]["properties"][field] = props2[field]
        
        # Merge required fields (only if required in both)
        req1 = set(schema1.get("items", {}).get("required", []))
        req2 = set(schema2.get("items", {}).get("required", []))
        merged["items"]["required"] = list(req1 & req2)
        
        return merged
    
    def get_schema_summary(self, schema: Dict[str, Any]) -> str:
        """
        Get human-readable schema summary.
        
        Args:
            schema: JSON Schema
            
        Returns:
            Summary string
        """
        item_schema = schema.get("items", {})
        properties = item_schema.get("properties", {})
        required = item_schema.get("required", [])
        
        summary = f"Schema with {len(properties)} fields:\n"
        
        for field, prop in properties.items():
            is_required = "required" if field in required else "optional"
            field_type = prop.get("type", "unknown")
            summary += f"  - {field} ({field_type}, {is_required})\n"
        
        return summary.strip()


def create_schema_builder() -> SchemaBuilder:
    """
    Factory function to create SchemaBuilder instance.
    
    Returns:
        SchemaBuilder instance
    """
    return SchemaBuilder()
