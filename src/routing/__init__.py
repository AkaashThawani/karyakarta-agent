"""
Tool Routing System

Intelligent tool selection and routing with multiple strategies.

Classes:
    - ToolCategory: Categories for organizing tools
    - CostLevel: Cost levels for tool usage
    - ToolMetadata: Metadata about a tool
    - ToolRegistry: Central registry for all tools
    - RoutingStrategy: Strategies for tool selection
    - ToolRouter: Routes tasks to appropriate tools

Usage:
    from src.routing import ToolRegistry, ToolRouter, ToolCategory, RoutingStrategy
    
    # Create registry
    registry = ToolRegistry()
    registry.register(
        name="google_search",
        description="Search the web",
        capabilities={"search", "web"},
        category=ToolCategory.SEARCH
    )
    
    # Create router
    router = ToolRouter(registry, strategy=RoutingStrategy.BALANCED)
    
    # Route a task
    tool = router.route(task)
"""

from src.routing.tool_registry import (
    ToolCategory,
    CostLevel,
    ToolMetadata,
    ToolRegistry,
)

from src.routing.tool_router import (
    RoutingStrategy,
    ToolRouter,
)

__all__ = [
    # Registry
    "ToolCategory",
    "CostLevel",
    "ToolMetadata",
    "ToolRegistry",
    
    # Router
    "RoutingStrategy",
    "ToolRouter",
]
