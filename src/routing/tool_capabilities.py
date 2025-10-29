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
    
    Returns:
        dict: Complete tool registry
    """
    registry_path = os.path.join(os.path.dirname(__file__), "..", "..", "tool_registry.json")
    
    try:
        with open(registry_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[REGISTRY] Warning: tool_registry.json not found at {registry_path}")
        print("[REGISTRY] Falling back to static registry")
        return _get_fallback_registry()
    except json.JSONDecodeError as e:
        print(f"[REGISTRY] Error parsing tool_registry.json: {e}")
        print("[REGISTRY] Falling back to static registry")
        return _get_fallback_registry()


def _get_fallback_registry() -> Dict[str, Dict[str, Any]]:
    """
    Fallback registry if JSON file not found.
    
    Returns:
        dict: Basic tool registry
    """
    return {
    "playwright_execute": {
        "description": "Universal browser automation tool - execute any Playwright Page method",
        "capabilities": [
            "Navigate to URLs",
            "Click elements",
            "Fill form fields",
            "Press keyboard keys",
            "Take screenshots",
            "Extract page content",
            "Wait for elements",
            "Execute JavaScript"
        ],
        "actions": [
            "goto", "click", "fill", "press", "hover",
            "screenshot", "content", "inner_text",
            "wait_for_selector", "evaluate"
        ],
        "keywords": [
            "go to", "navigate", "visit", "open",
            "click", "press", "type", "fill", "enter",
            "search", "submit", "screenshot", "capture",
            "scroll", "hover", "wait for"
        ],
        "parameter_types": {
            "url": "string - URL to navigate to",
            "method": "string - Playwright method name (required)",
            "selector": "string - CSS selector for element",
            "args": "dict - Additional method arguments"
        },
        "examples": [
            {
                "task": "Go to google.com",
                "subtasks": [
                    {"tool": "playwright_execute", "action": "goto", "parameters": {"url": "https://google.com", "method": "goto", "args": {}}}
                ]
            },
            {
                "task": "Go to youtube.com and search for cats",
                "subtasks": [
                    {"tool": "playwright_execute", "action": "goto", "parameters": {"url": "https://youtube.com", "method": "goto", "args": {}}},
                    {"tool": "playwright_execute", "action": "fill", "parameters": {"method": "fill", "selector": "input[name='search']", "args": {"value": "cats"}}},
                    {"tool": "playwright_execute", "action": "press", "parameters": {"method": "press", "selector": "input[name='search']", "args": {"key": "Enter"}}}
                ]
            },
            {
                "task": "Fill form with name John and email john@example.com then submit",
                "subtasks": [
                    {"tool": "playwright_execute", "action": "fill", "parameters": {"method": "fill", "selector": "input[name='name']", "args": {"value": "John"}}},
                    {"tool": "playwright_execute", "action": "fill", "parameters": {"method": "fill", "selector": "input[name='email']", "args": {"value": "john@example.com"}}},
                    {"tool": "playwright_execute", "action": "click", "parameters": {"method": "click", "selector": "button[type='submit']", "args": {}}}
                ]
            }
        ]
    },
    
    "google_search": {
        "description": "Search the web using Google",
        "capabilities": [
            "Web search",
            "Find information online",
            "Get search results with URLs"
        ],
        "actions": ["query"],
        "keywords": ["search", "find", "look up", "google", "query"],
        "parameter_types": {
            "query": "string - Search query (required)"
        },
        "examples": [
            {
                "task": "Search for Python tutorials",
                "subtasks": [
                    {"tool": "google_search", "action": "query", "parameters": {"query": "Python tutorials"}}
                ]
            }
        ]
    },
    
    "browse_website": {
        "description": "Scrape content from a website",
        "capabilities": [
            "Fetch webpage content",
            "Extract HTML",
            "Get page text"
        ],
        "actions": ["scrape"],
        "keywords": ["browse", "scrape", "fetch", "get content from"],
        "parameter_types": {
            "url": "string - URL to browse (required)"
        },
        "examples": [
            {
                "task": "Get content from example.com",
                "subtasks": [
                    {"tool": "browse_website", "action": "scrape", "parameters": {"url": "https://example.com"}}
                ]
            }
        ]
    },
    
    "calculator": {
        "description": "Perform mathematical calculations",
        "capabilities": [
            "Basic arithmetic",
            "Mathematical expressions",
            "Numerical computations"
        ],
        "actions": ["calculate"],
        "keywords": ["calculate", "compute", "math", "add", "subtract", "multiply", "divide"],
        "parameter_types": {
            "expression": "string - Mathematical expression (required)"
        },
        "examples": [
            {
                "task": "Calculate 25 * 4 + 10",
                "subtasks": [
                    {"tool": "calculator", "action": "calculate", "parameters": {"expression": "25 * 4 + 10"}}
                ]
            }
        ]
    }
}


# Load registry at module level
TOOL_REGISTRY = load_tool_registry()


def get_tool_registry() -> Dict[str, Dict[str, Any]]:
    """Get the complete tool registry."""
    return TOOL_REGISTRY


def get_tool_capabilities(tool_name: str) -> Dict[str, Any]:
    """Get capabilities for a specific tool."""
    return TOOL_REGISTRY.get(tool_name, {})


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
