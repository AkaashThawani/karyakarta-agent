"""
Tool Capabilities Registry

Loads tool registry from dynamically generated JSON file.
Run generate_tool_registry.py to update the registry.
"""

from typing import Dict, List, Any
import json
import os


def load_tool_registry() -> Dict[str, Dict[str, Any]]:
    """
    Load tool registry from JSON file.
    Filters out disabled tools (those with enabled=false or starting with _).
    
    Returns:
        dict: Tool registry with only enabled tools
        
    Raises:
        FileNotFoundError: If tool_registry.json is not found
        json.JSONDecodeError: If tool_registry.json is invalid
    """
    registry_path = os.path.join(os.path.dirname(__file__), "..", "..", "tool_registry.json")
    
    try:
        with open(registry_path, 'r') as f:
            full_registry = json.load(f)
        
        # Filter out disabled tools and metadata entries
        enabled_registry = {
            name: data 
            for name, data in full_registry.items() 
            if isinstance(data, dict) and data.get("enabled", True) and not name.startswith("_") and not name.startswith("$")
        }
        
        print(f"[REGISTRY] Loaded {len(enabled_registry)}/{len(full_registry)} enabled tools")
        return enabled_registry
        
    except FileNotFoundError:
        print(f"[REGISTRY] ERROR: tool_registry.json not found at {registry_path}")
        print("[REGISTRY] This is a deployment error - registry file must exist")
        raise
    except json.JSONDecodeError as e:
        print(f"[REGISTRY] ERROR: Invalid JSON in tool_registry.json: {e}")
        raise



# Load registry at module level
TOOL_REGISTRY = load_tool_registry()


def get_tool_registry() -> Dict[str, Dict[str, Any]]:
    """Get the complete tool registry."""
    return TOOL_REGISTRY


def get_tool_capabilities(tool_name: str) -> Dict[str, Any]:
    """
    Get essential capabilities for a specific tool (LLM-optimized).
    Returns only the minimal information needed, not the full registry entry.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Dict with only description, category, and enabled status
    """
    full_info = TOOL_REGISTRY.get(tool_name, {})
    
    if not full_info:
        return {}
    
    # Return only essential fields for LLM consumption
    return {
        "description": full_info.get("description", ""),
        "category": full_info.get("category", ""),
        "enabled": full_info.get("enabled", True)
    }


def get_all_tool_keywords() -> Dict[str, List[str]]:
    """Get keywords mapped to tools."""
    return {tool: info.get("keywords", []) for tool, info in TOOL_REGISTRY.items() if "keywords" in info}


def format_registry_for_llm() -> str:
    """Format registry for LLM consumption."""
    formatted = "# Available Tools\n\n"
    
    for tool_name, info in TOOL_REGISTRY.items():
        # Handle both old format (with capabilities) and new format (without)
        if "capabilities" in info:
            # Old format
            formatted += f"## {tool_name}\n"
            formatted += f"**Description:** {info['description']}\n\n"
            formatted += f"**Capabilities:**\n"
            for cap in info['capabilities']:
                formatted += f"- {cap}\n"
            formatted += f"\n**Actions:** {', '.join(info['actions'])}\n"
            formatted += f"**Keywords:** {', '.join(info['keywords'])}\n\n"
            
            formatted += "**Parameters:**\n"
            for param, desc in info['parameter_types'].items():
                formatted += f"- `{param}`: {desc}\n"
            
            formatted += "\n**Example:**\n"
            if info['examples']:
                example = info['examples'][0]
                formatted += f"Task: \"{example['task']}\"\n"
                formatted += "Subtasks:\n```json\n"
                import json
                formatted += json.dumps(example['subtasks'], indent=2)
                formatted += "\n```\n\n"
        else:
            # New format from generated registry
            formatted += f"## {tool_name}\n"
            formatted += f"**Description:** {info.get('description', 'No description')}\n\n"
            formatted += f"**Tool:** {info.get('tool', 'unknown')}\n"
            formatted += f"**Method:** {info.get('method', 'unknown')}\n"
            formatted += f"**Actions:** {', '.join(info.get('actions', []))}\n"
            formatted += f"**Keywords:** {', '.join(info.get('keywords', []))}\n"
            formatted += f"**Requires Selector:** {info.get('requires_selector', False)}\n\n"
    
    return formatted
