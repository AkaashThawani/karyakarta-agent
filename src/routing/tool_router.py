"""
Tool Router - Intelligent Tool Selection

Routes tasks to appropriate tools based on various strategies
including capability matching, cost optimization, and load balancing.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from src.routing.tool_registry import ToolRegistry, ToolMetadata, ToolCategory, CostLevel
from src.agents.base_agent import AgentTask


class RoutingStrategy(Enum):
    """Strategies for tool selection."""
    CAPABILITY = "capability"  # Match by capability only
    BEST_PERFORMANCE = "best_performance"  # Optimize for speed and reliability
    LOWEST_COST = "lowest_cost"  # Minimize cost
    BALANCED = "balanced"  # Balance cost, speed, reliability
    ROUND_ROBIN = "round_robin"  # Distribute load evenly
    LEAST_USED = "least_used"  # Use least utilized tool


class ToolRouter:
    """
    Routes tasks to appropriate tools using various strategies.
    
    Example:
        registry = ToolRegistry()
        router = ToolRouter(registry, strategy=RoutingStrategy.BALANCED)
        
        task = AgentTask(
            task_type="search",
            description="Find information",
            parameters={"query": "Python"}
        )
        
        # Route to best tool
        tool = router.route(task)
        
        # Or get multiple options with fallbacks
        tools = router.route_with_fallback(task, max_options=3)
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ):
        """
        Initialize router.
        
        Args:
            registry: Tool registry to use
            strategy: Default routing strategy
        """
        self.registry = registry
        self.strategy = strategy
        self.round_robin_state: Dict[str, int] = {}  # For round-robin strategy
    
    def route(
        self,
        task: AgentTask,
        strategy: Optional[RoutingStrategy] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[ToolMetadata]:
        """
        Route a task to the best tool.
        
        Args:
            task: Task to route
            strategy: Override default strategy
            constraints: Optional constraints:
                - max_cost: Maximum cost level
                - min_reliability: Minimum reliability
                - required_capabilities: List of required capabilities
                - exclude_tools: List of tool names to exclude
                
        Returns:
            Best ToolMetadata or None if no suitable tool found
        """
        strategy = strategy or self.strategy
        constraints = constraints or {}
        
        # Find candidate tools
        candidates = self._find_candidates(task, constraints)
        
        if not candidates:
            return None
        
        # Apply routing strategy
        if strategy == RoutingStrategy.CAPABILITY:
            return candidates[0]  # First match
        
        elif strategy == RoutingStrategy.BEST_PERFORMANCE:
            return self._select_best_performance(candidates)
        
        elif strategy == RoutingStrategy.LOWEST_COST:
            return self._select_lowest_cost(candidates)
        
        elif strategy == RoutingStrategy.BALANCED:
            return self._select_balanced(candidates)
        
        elif strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(candidates, task.task_type)
        
        elif strategy == RoutingStrategy.LEAST_USED:
            return self._select_least_used(candidates)
        
        return candidates[0]
    
    def route_with_fallback(
        self,
        task: AgentTask,
        max_options: int = 3,
        strategy: Optional[RoutingStrategy] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> List[ToolMetadata]:
        """
        Route with multiple fallback options.
        
        Args:
            task: Task to route
            max_options: Maximum number of fallback options
            strategy: Override default strategy
            constraints: Optional constraints
            
        Returns:
            List of ToolMetadata in priority order
        """
        strategy = strategy or self.strategy
        constraints = constraints or {}
        
        candidates = self._find_candidates(task, constraints)
        
        if not candidates:
            return []
        
        # Sort candidates by strategy
        if strategy == RoutingStrategy.BEST_PERFORMANCE:
            candidates.sort(
                key=lambda t: (t.reliability, -t.avg_latency),
                reverse=True
            )
        elif strategy == RoutingStrategy.LOWEST_COST:
            cost_order = {
                CostLevel.FREE: 0,
                CostLevel.LOW: 1,
                CostLevel.MEDIUM: 2,
                CostLevel.HIGH: 3,
                CostLevel.PREMIUM: 4
            }
            candidates.sort(key=lambda t: cost_order[t.cost])
        elif strategy == RoutingStrategy.BALANCED:
            candidates.sort(key=lambda t: self._calculate_score(t), reverse=True)
        
        return candidates[:max_options]
    
    def _find_candidates(
        self,
        task: AgentTask,
        constraints: Dict[str, Any]
    ) -> List[ToolMetadata]:
        """
        Find candidate tools for a task.
        
        Args:
            task: Task to find tools for
            constraints: Constraints to apply
            
        Returns:
            List of candidate ToolMetadata objects
        """
        # Start with task type as capability
        candidates = self.registry.find_by_capability(task.task_type)
        
        # If no direct match, try searching
        if not candidates:
            candidates = self.registry.search(task.description)
        
        # Apply constraints
        if "max_cost" in constraints:
            cost_order = {
                CostLevel.FREE: 0,
                CostLevel.LOW: 1,
                CostLevel.MEDIUM: 2,
                CostLevel.HIGH: 3,
                CostLevel.PREMIUM: 4
            }
            max_cost = constraints["max_cost"]
            max_cost_val = cost_order.get(max_cost, 4)
            candidates = [
                c for c in candidates
                if cost_order[c.cost] <= max_cost_val
            ]
        
        if "min_reliability" in constraints:
            min_rel = constraints["min_reliability"]
            candidates = [c for c in candidates if c.reliability >= min_rel]
        
        if "required_capabilities" in constraints:
            required = set(constraints["required_capabilities"])
            candidates = [
                c for c in candidates
                if required.issubset(c.capabilities)
            ]
        
        if "exclude_tools" in constraints:
            exclude = set(constraints["exclude_tools"])
            candidates = [c for c in candidates if c.name not in exclude]
        
        return candidates
    
    def _select_best_performance(
        self,
        candidates: List[ToolMetadata]
    ) -> ToolMetadata:
        """Select tool with best performance (reliability and speed)."""
        return max(
            candidates,
            key=lambda t: (t.reliability / 100.0) * (1.0 / max(t.avg_latency, 0.1))
        )
    
    def _select_lowest_cost(
        self,
        candidates: List[ToolMetadata]
    ) -> ToolMetadata:
        """Select tool with lowest cost."""
        cost_order = {
            CostLevel.FREE: 0,
            CostLevel.LOW: 1,
            CostLevel.MEDIUM: 2,
            CostLevel.HIGH: 3,
            CostLevel.PREMIUM: 4
        }
        return min(candidates, key=lambda t: cost_order[t.cost])
    
    def _select_balanced(
        self,
        candidates: List[ToolMetadata]
    ) -> ToolMetadata:
        """Select tool with balanced score."""
        return max(candidates, key=self._calculate_score)
    
    def _calculate_score(self, tool: ToolMetadata) -> float:
        """Calculate balanced score for a tool."""
        cost_score = {
            CostLevel.FREE: 1.0,
            CostLevel.LOW: 0.8,
            CostLevel.MEDIUM: 0.6,
            CostLevel.HIGH: 0.4,
            CostLevel.PREMIUM: 0.2
        }[tool.cost]
        
        reliability_score = tool.reliability / 100.0
        latency_score = max(0, 1.0 - (tool.avg_latency / 10.0))
        
        return (
            reliability_score * 0.5 +
            latency_score * 0.3 +
            cost_score * 0.2
        )
    
    def _select_round_robin(
        self,
        candidates: List[ToolMetadata],
        task_type: str
    ) -> ToolMetadata:
        """Select tool using round-robin."""
        if task_type not in self.round_robin_state:
            self.round_robin_state[task_type] = 0
        
        index = self.round_robin_state[task_type] % len(candidates)
        self.round_robin_state[task_type] += 1
        
        return candidates[index]
    
    def _select_least_used(
        self,
        candidates: List[ToolMetadata]
    ) -> ToolMetadata:
        """Select least used tool."""
        def get_usage(tool: ToolMetadata) -> int:
            stats = self.registry.get_stats(tool.name)
            return stats["total_uses"] if stats else 0
        
        return min(candidates, key=get_usage)
    
    def suggest_alternative(
        self,
        task: AgentTask,
        failed_tool: str
    ) -> Optional[ToolMetadata]:
        """
        Suggest alternative tool after a failure.
        
        Args:
            task: Original task
            failed_tool: Name of tool that failed
            
        Returns:
            Alternative ToolMetadata or None
        """
        constraints = {"exclude_tools": [failed_tool]}
        return self.route(task, constraints=constraints)
    
    def get_routing_plan(
        self,
        task: AgentTask,
        max_attempts: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Create a routing plan with fallbacks.
        
        Args:
            task: Task to plan for
            max_attempts: Maximum number of attempts
            
        Returns:
            List of routing options with metadata
        """
        plan = []
        exclude = []
        
        for attempt in range(max_attempts):
            constraints = {"exclude_tools": exclude}
            tool = self.route(task, constraints=constraints)
            
            if not tool:
                break
            
            plan.append({
                "attempt": attempt + 1,
                "tool_name": tool.name,
                "reliability": tool.reliability,
                "avg_latency": tool.avg_latency,
                "cost": tool.cost.value,
                "reason": self._get_selection_reason(tool, attempt)
            })
            
            exclude.append(tool.name)
        
        return plan
    
    def _get_selection_reason(
        self,
        tool: ToolMetadata,
        attempt: int
    ) -> str:
        """Get human-readable reason for tool selection."""
        if attempt == 0:
            return f"Primary choice: {self.strategy.value} strategy"
        else:
            return f"Fallback option #{attempt + 1}"
    
    def set_strategy(self, strategy: RoutingStrategy) -> None:
        """
        Change default routing strategy.
        
        Args:
            strategy: New routing strategy
        """
        self.strategy = strategy
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """
        Get routing statistics summary.
        
        Returns:
            Dictionary of routing stats
        """
        all_tools = self.registry.list_all()
        
        if not all_tools:
            return {"total_tools": 0}
        
        total_uses = sum(
            self.registry.get_stats(t.name)["total_uses"] # type: ignore
            for t in all_tools
            if self.registry.get_stats(t.name) is not None
        )
        
        avg_reliability = sum(t.reliability for t in all_tools) / len(all_tools)
        avg_latency = sum(t.avg_latency for t in all_tools) / len(all_tools)
        
        return {
            "total_tools": len(all_tools),
            "total_uses": total_uses,
            "avg_reliability": round(avg_reliability, 2),
            "avg_latency": round(avg_latency, 2),
            "strategy": self.strategy.value
        }
