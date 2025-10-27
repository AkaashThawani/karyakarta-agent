"""
Tool Registry - Centralized Tool Management

Maintains a registry of all available tools with metadata including
capabilities, performance characteristics, and availability.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class ToolCategory(Enum):
    """Categories of tools for organization."""
    SEARCH = "search"
    SCRAPING = "scraping"
    DATA_PROCESSING = "data_processing"
    CALCULATION = "calculation"
    COMMUNICATION = "communication"
    FILE_OPERATION = "file_operation"
    API = "api"
    OTHER = "other"


class CostLevel(Enum):
    """Cost levels for tool usage."""
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


@dataclass
class ToolMetadata:
    """
    Metadata about a tool.
    
    Contains information about tool capabilities, performance,
    and operational characteristics.
    """
    name: str
    description: str
    capabilities: Set[str] = field(default_factory=set)
    category: ToolCategory = ToolCategory.OTHER
    cost: CostLevel = CostLevel.FREE
    avg_latency: float = 0.0  # Average latency in seconds
    reliability: float = 100.0  # Success rate percentage
    max_concurrent: int = 1  # Max concurrent executions
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # Requests per minute
    tags: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    enabled: bool = True
    
    def __post_init__(self):
        """Ensure capabilities and tags are sets."""
        if not isinstance(self.capabilities, set):
            self.capabilities = set(self.capabilities)
        if not isinstance(self.tags, set):
            self.tags = set(self.tags)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "category": self.category.value,
            "cost": self.cost.value,
            "avg_latency": self.avg_latency,
            "reliability": self.reliability,
            "max_concurrent": self.max_concurrent,
            "requires_auth": self.requires_auth,
            "rate_limit": self.rate_limit,
            "tags": list(self.tags),
            "version": self.version,
            "enabled": self.enabled
        }


class ToolRegistry:
    """
    Central registry for all tools.
    
    Maintains metadata about tools and provides query capabilities.
    
    Example:
        registry = ToolRegistry()
        
        # Register a tool
        registry.register(
            name="google_search",
            description="Search the web using Google",
            capabilities={"search", "web", "current_info"},
            category=ToolCategory.SEARCH,
            cost=CostLevel.FREE,
            avg_latency=1.5,
            reliability=95.0
        )
        
        # Find tools by capability
        search_tools = registry.find_by_capability("search")
        
        # Get best tool for capability
        best = registry.get_best_tool("search", optimize_for="latency")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self.tools: Dict[str, ToolMetadata] = {}
        self.capability_index: Dict[str, Set[str]] = {}
        self.category_index: Dict[ToolCategory, Set[str]] = {}
        self.stats: Dict[str, Dict[str, Any]] = {}
    
    def register(
        self,
        name: str,
        description: str,
        capabilities: Set[str],
        category: ToolCategory = ToolCategory.OTHER,
        cost: CostLevel = CostLevel.FREE,
        avg_latency: float = 0.0,
        reliability: float = 100.0,
        max_concurrent: int = 1,
        requires_auth: bool = False,
        rate_limit: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        version: str = "1.0.0"
    ) -> bool:
        """
        Register a tool in the registry.
        
        Args:
            name: Unique tool name
            description: Tool description
            capabilities: Set of capabilities
            category: Tool category
            cost: Cost level
            avg_latency: Average latency in seconds
            reliability: Success rate percentage
            max_concurrent: Max concurrent executions
            requires_auth: Whether tool requires authentication
            rate_limit: Rate limit (requests per minute)
            tags: Additional tags
            version: Tool version
            
        Returns:
            True if registered successfully
        """
        if name in self.tools:
            print(f"Warning: Tool '{name}' already registered. Updating...")
        
        metadata = ToolMetadata(
            name=name,
            description=description,
            capabilities=capabilities,
            category=category,
            cost=cost,
            avg_latency=avg_latency,
            reliability=reliability,
            max_concurrent=max_concurrent,
            requires_auth=requires_auth,
            rate_limit=rate_limit,
            tags=tags or set(),
            version=version
        )
        
        self.tools[name] = metadata
        
        # Update capability index
        for capability in capabilities:
            if capability not in self.capability_index:
                self.capability_index[capability] = set()
            self.capability_index[capability].add(name)
        
        # Update category index
        if category not in self.category_index:
            self.category_index[category] = set()
        self.category_index[category].add(name)
        
        # Initialize stats
        self.stats[name] = {
            "total_uses": 0,
            "successful_uses": 0,
            "failed_uses": 0,
            "total_latency": 0.0
        }
        
        return True
    
    def unregister(self, name: str) -> bool:
        """
        Remove a tool from registry.
        
        Args:
            name: Tool name to remove
            
        Returns:
            True if removed, False if not found
        """
        if name not in self.tools:
            return False
        
        metadata = self.tools[name]
        
        # Remove from capability index
        for capability in metadata.capabilities:
            if capability in self.capability_index:
                self.capability_index[capability].discard(name)
                if not self.capability_index[capability]:
                    del self.capability_index[capability]
        
        # Remove from category index
        if metadata.category in self.category_index:
            self.category_index[metadata.category].discard(name)
        
        # Remove tool and stats
        del self.tools[name]
        if name in self.stats:
            del self.stats[name]
        
        return True
    
    def get(self, name: str) -> Optional[ToolMetadata]:
        """
        Get metadata for a specific tool.
        
        Args:
            name: Tool name
            
        Returns:
            ToolMetadata or None if not found
        """
        return self.tools.get(name)
    
    def find_by_capability(self, capability: str) -> List[ToolMetadata]:
        """
        Find all tools with a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of ToolMetadata objects
        """
        tool_names = self.capability_index.get(capability, set())
        return [self.tools[name] for name in tool_names if self.tools[name].enabled]
    
    def find_by_category(self, category: ToolCategory) -> List[ToolMetadata]:
        """
        Find all tools in a category.
        
        Args:
            category: Category to search
            
        Returns:
            List of ToolMetadata objects
        """
        tool_names = self.category_index.get(category, set())
        return [self.tools[name] for name in tool_names if self.tools[name].enabled]
    
    def find_by_tag(self, tag: str) -> List[ToolMetadata]:
        """
        Find tools with a specific tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of ToolMetadata objects
        """
        return [
            metadata for metadata in self.tools.values()
            if tag in metadata.tags and metadata.enabled
        ]
    
    def get_best_tool(
        self,
        capability: str,
        optimize_for: str = "reliability"
    ) -> Optional[ToolMetadata]:
        """
        Get the best tool for a capability based on optimization criteria.
        
        Args:
            capability: Required capability
            optimize_for: What to optimize for:
                - "reliability": Highest success rate
                - "latency": Fastest response
                - "cost": Lowest cost
                - "balanced": Balance of all factors
                
        Returns:
            Best ToolMetadata or None if no tools found
        """
        tools = self.find_by_capability(capability)
        
        if not tools:
            return None
        
        if optimize_for == "reliability":
            return max(tools, key=lambda t: t.reliability)
        elif optimize_for == "latency":
            return min(tools, key=lambda t: t.avg_latency)
        elif optimize_for == "cost":
            cost_order = {
                CostLevel.FREE: 0,
                CostLevel.LOW: 1,
                CostLevel.MEDIUM: 2,
                CostLevel.HIGH: 3,
                CostLevel.PREMIUM: 4
            }
            return min(tools, key=lambda t: cost_order[t.cost])
        elif optimize_for == "balanced":
            # Score based on multiple factors
            def score(tool: ToolMetadata) -> float:
                cost_score = {
                    CostLevel.FREE: 1.0,
                    CostLevel.LOW: 0.8,
                    CostLevel.MEDIUM: 0.6,
                    CostLevel.HIGH: 0.4,
                    CostLevel.PREMIUM: 0.2
                }[tool.cost]
                
                reliability_score = tool.reliability / 100.0
                latency_score = max(0, 1.0 - (tool.avg_latency / 10.0))
                
                return (reliability_score * 0.5 + 
                       latency_score * 0.3 + 
                       cost_score * 0.2)
            
            return max(tools, key=score)
        
        return tools[0]
    
    def search(
        self,
        query: str,
        category: Optional[ToolCategory] = None,
        cost_limit: Optional[CostLevel] = None,
        min_reliability: float = 0.0
    ) -> List[ToolMetadata]:
        """
        Search for tools matching criteria.
        
        Args:
            query: Search query (matches name, description, capabilities, tags)
            category: Optional category filter
            cost_limit: Maximum cost level
            min_reliability: Minimum reliability percentage
            
        Returns:
            List of matching ToolMetadata objects
        """
        results = []
        query_lower = query.lower()
        
        cost_order = {
            CostLevel.FREE: 0,
            CostLevel.LOW: 1,
            CostLevel.MEDIUM: 2,
            CostLevel.HIGH: 3,
            CostLevel.PREMIUM: 4
        }
        cost_limit_value = cost_order.get(cost_limit, 4) if cost_limit else 4
        
        for metadata in self.tools.values():
            if not metadata.enabled:
                continue
            
            # Category filter
            if category and metadata.category != category:
                continue
            
            # Cost filter
            if cost_order[metadata.cost] > cost_limit_value:
                continue
            
            # Reliability filter
            if metadata.reliability < min_reliability:
                continue
            
            # Query match
            if (query_lower in metadata.name.lower() or
                query_lower in metadata.description.lower() or
                any(query_lower in cap.lower() for cap in metadata.capabilities) or
                any(query_lower in tag.lower() for tag in metadata.tags)):
                results.append(metadata)
        
        return results
    
    def update_stats(
        self,
        tool_name: str,
        success: bool,
        latency: float
    ) -> None:
        """
        Update tool usage statistics.
        
        Args:
            tool_name: Name of tool used
            success: Whether execution succeeded
            latency: Execution latency in seconds
        """
        if tool_name not in self.stats:
            return
        
        stats = self.stats[tool_name]
        stats["total_uses"] += 1
        stats["total_latency"] += latency
        
        if success:
            stats["successful_uses"] += 1
        else:
            stats["failed_uses"] += 1
        
        # Update metadata with moving average
        if tool_name in self.tools:
            metadata = self.tools[tool_name]
            total = stats["total_uses"]
            
            # Update average latency
            metadata.avg_latency = stats["total_latency"] / total
            
            # Update reliability
            metadata.reliability = (stats["successful_uses"] / total) * 100
    
    def get_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a tool.
        
        Args:
            tool_name: Tool name
            
        Returns:
            Statistics dictionary or None
        """
        if tool_name not in self.stats:
            return None
        
        stats = self.stats[tool_name].copy()
        
        if stats["total_uses"] > 0:
            stats["success_rate"] = (stats["successful_uses"] / stats["total_uses"]) * 100
            stats["avg_latency"] = stats["total_latency"] / stats["total_uses"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_latency"] = 0.0
        
        return stats
    
    def list_all(self, enabled_only: bool = True) -> List[ToolMetadata]:
        """
        List all tools in registry.
        
        Args:
            enabled_only: Only return enabled tools
            
        Returns:
            List of all ToolMetadata objects
        """
        if enabled_only:
            return [m for m in self.tools.values() if m.enabled]
        return list(self.tools.values())
    
    def enable_tool(self, name: str) -> bool:
        """
        Enable a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if successful
        """
        if name in self.tools:
            self.tools[name].enabled = True
            return True
        return False
    
    def disable_tool(self, name: str) -> bool:
        """
        Disable a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if successful
        """
        if name in self.tools:
            self.tools[name].enabled = False
            return True
        return False
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get registry summary.
        
        Returns:
            Summary statistics
        """
        enabled_tools = [t for t in self.tools.values() if t.enabled]
        
        return {
            "total_tools": len(self.tools),
            "enabled_tools": len(enabled_tools),
            "categories": {
                cat.value: len(tools)
                for cat, tools in self.category_index.items()
            },
            "capabilities": list(self.capability_index.keys()),
            "total_capabilities": len(self.capability_index)
        }
