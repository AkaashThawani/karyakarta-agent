"""
Agent Helper Utilities

Extracted from the multi-agent system for reuse.
These are pure utility functions that can be used independently.
"""

from typing import List, Dict, Any, Optional
import re


def extract_required_fields_from_query(query: str, llm_service: Any = None) -> List[str]:
    """
    Extract field requirements from natural language query.
    
    Args:
        query: User query (e.g., "Find iPhone with price and specs")
        llm_service: Optional LLM service for intelligent extraction
        
    Returns:
        List of field names (e.g., ["name", "price", "specs"])
    """
    if llm_service:
        try:
            schema = llm_service.get_field_extraction_schema()
            prompt = f"""Extract field requirements from: "{query}"
            
Consider what data fields would be most useful."""
            
            result = llm_service.invoke_with_schema(
                prompt=prompt,
                schema=schema,
                schema_name="field_extraction"
            )
            
            if result and isinstance(result, dict):
                user_fields = result.get("user_requested", [])
                suggested_fields = result.get("suggested", [])
                return list(dict.fromkeys(user_fields + suggested_fields))  # Remove duplicates
        except Exception as e:
            print(f"[AGENT_HELPERS] LLM field extraction failed: {e}")
    
    # Fallback: keyword-based extraction
    fields = ["name"]
    query_lower = query.lower()
    
    if "price" in query_lower or "cost" in query_lower:
        fields.append("price")
    if "rating" in query_lower or "review" in query_lower:
        fields.append("rating")
    if "spec" in query_lower or "detail" in query_lower:
        fields.append("specifications")
    if "location" in query_lower or "address" in query_lower:
        fields.append("location")
    
    return fields


def extract_query_params_from_description(description: str, llm_service: Any = None) -> Dict[str, Any]:
    """
    Extract API query parameters from natural language.
    
    Args:
        description: Task description (e.g., "Get latest 10 posts")
        llm_service: Optional LLM service
        
    Returns:
        Dict of parameters (e.g., {"limit": 10, "sort": "id", "order": "desc"})
    """
    if llm_service:
        try:
            prompt = f"""Extract API parameters from: "{description}"
            
Common patterns:
- "latest N" → {{"limit": N, "sort": "id", "order": "desc"}}
- "top N" → {{"limit": N, "sort": "rank", "order": "asc"}}

Return ONLY JSON object or {{}}.

JSON:"""
            
            model = llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            json_match = re.search(r'\{.*\}', content.strip(), re.DOTALL)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[AGENT_HELPERS] Query param extraction failed: {e}")
    
    # Fallback: regex-based extraction
    params = {}
    
    # Extract "top/latest/first N" patterns
    quantity_match = re.search(r'(top|latest|first)\s+(\d+)', description.lower())
    if quantity_match:
        params["limit"] = int(quantity_match.group(2))
        if quantity_match.group(1) == "latest":
            params["sort"] = "date"
            params["order"] = "desc"
    
    return params


def evaluate_result_completeness(
    task_description: str,
    tool_result: Any,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluate if result is complete based on task requirements.
    
    Args:
        task_description: Original task (e.g., "Find top 10 items")
        tool_result: Tool execution result
        context: Optional context
        
    Returns:
        Dict with: {
            "complete": bool,
            "reason": str (if incomplete),
            "next_action": str (if incomplete),
            "coverage": str (e.g., "70%")
        }
    """
    completeness = {"complete": True, "coverage": "100%"}
    
    try:
        task_desc = task_description.lower()
        result_str = str(tool_result).lower() if tool_result else ""
        
        # Check quantity requirements
        quantity_match = re.search(r'(top|find|get|list)\s+(\d+)', task_desc)
        if quantity_match:
            requested_count = int(quantity_match.group(2))
            
            # Count items in result
            result_lines = tool_result.split('\n') if isinstance(tool_result, str) else []
            numbered_items = len(re.findall(r'^\d+[\.\)]\s+', str(tool_result), re.MULTILINE))
            list_items = len(re.findall(r'^[-\*]\s+', str(tool_result), re.MULTILINE))
            
            found_count = max(numbered_items, list_items)
            
            if found_count < requested_count and found_count > 0:
                coverage = int((found_count / requested_count) * 100)
                return {
                    "complete": False,
                    "reason": f"Found {found_count}/{requested_count} items",
                    "next_action": "search_more_sources",
                    "coverage": f"{coverage}%"
                }
        
        # Check for required fields
        if 'price' in task_desc and 'price' not in result_str and '$' not in result_str:
            return {
                "complete": False,
                "reason": "Missing price information",
                "next_action": "extract_more_details",
                "coverage": "75%"
            }
        
        # Check result size
        if isinstance(tool_result, str) and len(tool_result.strip()) < 50:
            if any(word in task_desc for word in ['find', 'search', 'get']):
                return {
                    "complete": False,
                    "reason": "Result too brief",
                    "next_action": "search_alternate_sources",
                    "coverage": "50%"
                }
    
    except Exception as e:
        print(f"[AGENT_HELPERS] Completeness evaluation failed: {e}")
    
    return completeness


def classify_tool_error(error: Optional[str]) -> tuple[str, bool]:
    """
    Classify error and determine if recoverable.
    
    Args:
        error: Error message
        
    Returns:
        Tuple of (error_type, is_recoverable)
        error_type: selector_not_found, timeout, network, validation, unknown
        is_recoverable: True if retrying/replanning might help
    """
    if not error:
        return ("unknown", False)
    
    error_lower = error.lower()
    
    # Selector/element not found - RECOVERABLE
    if any(k in error_lower for k in ['selector', 'locator', 'element not found', 'no such element']):
        return ("selector_not_found", True)
    
    # Timeout - RECOVERABLE
    if any(k in error_lower for k in ['timeout', 'timed out', 'exceeded']):
        return ("timeout", True)
    
    # Navigation - RECOVERABLE
    if any(k in error_lower for k in ['navigation', 'page', 'load']):
        return ("navigation", True)
    
    # Network - NOT RECOVERABLE (need user to fix)
    if any(k in error_lower for k in ['network', 'connection', 'dns', 'refused']):
        return ("network", False)
    
    # Validation - NOT RECOVERABLE (wrong parameters)
    if any(k in error_lower for k in ['validation', 'invalid', 'required']):
        return ("validation", False)
    
    return ("unknown", False)
