"""
One-Time Tool Registry Generator

Run this script to dynamically generate the tool registry JSON
that includes Playwright methods and all other tools.

Usage:
    python generate_tool_registry.py

Output:
    - Creates tool_registry.json with complete tool definitions
    - System loads this JSON at runtime
"""

import asyncio
import json
from playwright.async_api import async_playwright


# Playwright methods relevant for automation
RELEVANT_PLAYWRIGHT_METHODS = [
    "goto", "click", "fill", "press", "hover", "check", "uncheck",
    "select_option", "screenshot", "inner_text", "inner_html",
    "text_content", "get_attribute", "wait_for_selector",
    "wait_for_load_state", "wait_for_timeout", "evaluate", "evaluate_handle",
    "content", "query_selector", "query_selector_all", "dispatch_event",
    "focus", "is_visible", "is_hidden", "is_enabled", "is_disabled",
    "is_checked", "set_input_files", "dblclick", "tap", "reload",
    "go_back", "go_forward"
]

# Keywords that map to each Playwright method
PLAYWRIGHT_KEYWORD_MAP = {
    "goto": ["navigate", "go to", "visit", "open page", "browse to"],
    "click": ["click", "press button", "select", "tap on", "hit"],
    "fill": ["type", "enter text", "fill", "write", "input"],
    "press": ["press key", "hit enter", "keyboard", "key press"],
    "hover": ["hover", "mouse over", "mouseover"],
    "check": ["check", "tick", "select checkbox", "mark"],
    "uncheck": ["uncheck", "untick", "deselect checkbox", "unmark"],
    "select_option": ["select", "choose from dropdown", "pick option", "select from"],
    "screenshot": ["screenshot", "capture", "take picture", "snap"],
    "inner_text": ["get text", "read text", "inner text", "text of"],
    "inner_html": ["get html", "read html", "inner html"],
    "text_content": ["get content", "read text content", "text content"],
    "get_attribute": ["get attribute", "read attribute", "attribute of"],
    "wait_for_selector": ["wait for element", "wait for selector", "wait until"],
    "wait_for_load_state": ["wait for load", "wait for page", "wait until loaded"],
    "wait_for_timeout": ["wait", "pause", "delay", "sleep"],
    "evaluate": ["execute javascript", "run script", "evaluate", "run js"],
    "evaluate_handle": ["execute javascript", "get handle", "js handle"],
    "content": ["get html", "page content", "full html"],
    "query_selector": ["find element", "select element", "get element"],
    "query_selector_all": ["find all elements", "select all", "get all elements"],
    "dispatch_event": ["trigger event", "dispatch event", "fire event"],
    "focus": ["focus", "focus element", "set focus"],
    "is_visible": ["is visible", "check visibility", "visible"],
    "is_hidden": ["is hidden", "check hidden", "hidden"],
    "is_enabled": ["is enabled", "check enabled", "enabled"],
    "is_disabled": ["is disabled", "check disabled", "disabled"],
    "is_checked": ["is checked", "checkbox status", "checked"],
    "set_input_files": ["upload file", "set files", "attach file"],
    "dblclick": ["double click", "dblclick", "double tap"],
    "tap": ["tap", "touch tap", "mobile tap"],
    "reload": ["reload", "refresh", "refresh page"],
    "go_back": ["go back", "back", "navigate back"],
    "go_forward": ["go forward", "forward", "navigate forward"]
}

# Selector hints for methods that need selectors
DEFAULT_SELECTOR_HINTS = ["id", "class", "name", "placeholder", "type", "aria-label", "data-*"]

# Methods that don't require selectors
NO_SELECTOR_METHODS = [
    "goto", "screenshot", "evaluate", "content", "reload",
    "go_back", "go_forward", "wait_for_load_state", "wait_for_timeout"
]


async def generate_playwright_registry():
    """
    Dynamically generate Playwright tool registry by introspecting the API.
    
    Returns:
        dict: Playwright methods with actions, keywords, and selector hints
    """
    print("🔍 Introspecting Playwright API...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Get all callable methods on the page
        all_methods = [m for m in dir(page) if callable(getattr(page, m)) and not m.startswith("_")]
        
        playwright_registry = {}
        
        for method in RELEVANT_PLAYWRIGHT_METHODS:
            if method in all_methods:
                playwright_registry[f"playwright_{method}"] = {
                    "tool": "playwright_execute",
                    "method": method,
                    "description": f"Playwright Page.{method}() - Browser automation",
                    "actions": [method],
                    "selector_hints": [] if method in NO_SELECTOR_METHODS else DEFAULT_SELECTOR_HINTS,
                    "keywords": PLAYWRIGHT_KEYWORD_MAP.get(method, [method]),
                    "requires_selector": method not in NO_SELECTOR_METHODS
                }
        
        await browser.close()
        
    print(f"✅ Generated {len(playwright_registry)} Playwright methods")
    return playwright_registry


def generate_other_tools_registry():
    """
    Define other non-Playwright tools.
    
    Returns:
        dict: Other tools with their definitions
    """
    print("📝 Defining other tools...")
    
    other_tools = {
        "google_search": {
            "tool": "google_search",
            "method": "query",
            "description": "Search the web using Google",
            "actions": ["query", "search"],
            "selector_hints": [],
            "keywords": ["search", "google", "find", "lookup", "query", "look up"],
            "requires_selector": False,
            "parameters": {
                "query": "string - Search query (required)"
            }
        },
        "browse_website": {
            "tool": "browse_website",
            "method": "scrape",
            "description": "Scrape content from a website",
            "actions": ["scrape", "fetch"],
            "selector_hints": [],
            "keywords": ["browse", "scrape", "fetch", "get content from", "visit"],
            "requires_selector": False,
            "parameters": {
                "url": "string - URL to browse (required)"
            }
        },
        "calculator": {
            "tool": "calculator",
            "method": "calculate",
            "description": "Perform mathematical calculations",
            "actions": ["calculate", "compute"],
            "selector_hints": [],
            "keywords": ["calculate", "compute", "math", "add", "subtract", "multiply", "divide"],
            "requires_selector": False,
            "parameters": {
                "expression": "string - Mathematical expression (required)"
            }
        },
        "extract_data": {
            "tool": "extract_data",
            "method": "extract",
            "description": "Extract structured data from HTML",
            "actions": ["extract", "parse"],
            "selector_hints": ["css", "xpath"],
            "keywords": ["extract", "scrape", "parse", "get data", "read data"],
            "requires_selector": True,
            "parameters": {
                "data_type": "string - Type (json/html/xml/csv/table)",
                "content": "string - Content to extract from",
                "path": "string - Optional selector path"
            }
        }
    }
    
    print(f"✅ Defined {len(other_tools)} other tools")
    return other_tools


async def generate_complete_registry():
    """
    Generate complete tool registry combining Playwright and other tools.
    
    Returns:
        dict: Complete unified tool registry
    """
    print("\n" + "="*60)
    print("🚀 Generating Complete Tool Registry")
    print("="*60 + "\n")
    
    # Generate Playwright registry dynamically
    playwright_registry = await generate_playwright_registry()
    
    # Define other tools
    other_tools_registry = generate_other_tools_registry()
    
    # Combine all tools
    complete_registry = {
        **playwright_registry,
        **other_tools_registry
    }
    
    print(f"\n✨ Total tools in registry: {len(complete_registry)}")
    return complete_registry


def save_registry(registry, filename="tool_registry.json"):
    """Save registry to JSON file."""
    with open(filename, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"\n💾 Registry saved to: {filename}")


def main():
    """Main entry point."""
    filename = "tool_registry.json"
    
    # Generate registry
    registry = asyncio.run(generate_complete_registry())
    
    # Save to JSON
    save_registry(registry, filename)
    
    # Print summary
    print("\n" + "="*60)
    print("✅ Tool Registry Generation Complete!")
    print("="*60)
    print(f"\nThe system can now load '{filename}' at runtime.")
    print("Re-run this script when:")
    print("  - Playwright is upgraded")
    print("  - New tools are added")
    print("  - Keywords need updating")
    print()


if __name__ == "__main__":
    main()
