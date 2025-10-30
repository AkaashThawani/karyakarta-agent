"""
Learning Manager - Unified Tool Performance Tracking

Tracks success rates and performance of ALL tools across different sites.
Enables intelligent tool selection based on historical data.

Architecture:
- Records every tool execution (success/failure)
- Tracks performance metrics per site
- Recommends best tool for each task
- Integrates with selector_map and source_registry
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import json
from urllib.parse import urlparse
from collections import defaultdict


class ToolPerformanceTracker:
    """Track performance metrics for a specific tool on a specific site."""
    
    def __init__(self, tool_name: str, site: str):
        self.tool_name = tool_name
        self.site = site
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.total_response_time = 0.0
        self.last_success = None
        self.last_failure = None
        self.recent_successes = []  # Last 10 attempts
        
    def record_attempt(self, success: bool, response_time: float = 0.0):
        """Record a tool execution attempt."""
        self.total_attempts += 1
        
        if success:
            self.successful_attempts += 1
            self.last_success = datetime.now().isoformat()
        else:
            self.failed_attempts += 1
            self.last_failure = datetime.now().isoformat()
        
        self.total_response_time += response_time
        
        # Track recent success pattern (last 10)
        self.recent_successes.append(success)
        if len(self.recent_successes) > 10:
            self.recent_successes.pop(0)
    
    @property
    def success_rate(self) -> float:
        """Overall success rate (0.0 to 1.0)."""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts
    
    @property
    def recent_success_rate(self) -> float:
        """Recent success rate (last 10 attempts)."""
        if not self.recent_successes:
            return 0.0
        return sum(1 for s in self.recent_successes if s) / len(self.recent_successes)
    
    @property
    def avg_response_time(self) -> float:
        """Average response time in seconds."""
        if self.successful_attempts == 0:
            return 0.0
        return self.total_response_time / self.successful_attempts
    
    @property
    def reliability_score(self) -> float:
        """
        Composite score considering both success rate and recency.
        Recent success rate weighted more heavily.
        """
        overall = self.success_rate * 0.3
        recent = self.recent_success_rate * 0.7
        return overall + recent
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tool_name": self.tool_name,
            "site": self.site,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "success_rate": self.success_rate,
            "recent_success_rate": self.recent_success_rate,
            "avg_response_time": self.avg_response_time,
            "reliability_score": self.reliability_score,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "recent_successes": self.recent_successes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolPerformanceTracker':
        """Deserialize from dictionary."""
        tracker = cls(data["tool_name"], data["site"])
        tracker.total_attempts = data["total_attempts"]
        tracker.successful_attempts = data["successful_attempts"]
        tracker.failed_attempts = data["failed_attempts"]
        tracker.total_response_time = data.get("avg_response_time", 0.0) * data["successful_attempts"]
        tracker.last_success = data.get("last_success")
        tracker.last_failure = data.get("last_failure")
        tracker.recent_successes = data.get("recent_successes", [])
        return tracker


class LearningManager:
    """
    Unified learning manager for all tools.
    Tracks which tools work best on which sites.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "learning_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.cache_file = self.cache_dir / "tool_performance.json"
        
        # In-memory storage: {site: {tool_name: ToolPerformanceTracker}}
        self.performance: Dict[str, Dict[str, ToolPerformanceTracker]] = defaultdict(dict)
        
        # Load existing data
        self.load()
    
    def _extract_site(self, url: str) -> str:
        """Extract site domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return url
    
    def record_tool_execution(
        self,
        url: str,
        tool_name: str,
        success: bool,
        response_time: float = 0.0,
        action: Optional[str] = None
    ):
        """
        Record a tool execution result.
        
        Args:
            url: Site URL
            tool_name: Name of tool used
            success: Whether execution succeeded
            response_time: Time taken in seconds
            action: Optional action performed (click, fill, etc.)
        """
        site = self._extract_site(url)
        
        # Get or create tracker
        if tool_name not in self.performance[site]:
            self.performance[site][tool_name] = ToolPerformanceTracker(tool_name, site)
        
        tracker = self.performance[site][tool_name]
        tracker.record_attempt(success, response_time)
        
        print(f"[LEARNING] Recorded {tool_name} on {site}: "
              f"{'✅ Success' if success else '❌ Failure'} "
              f"(Success rate: {tracker.success_rate:.0%}, "
              f"Recent: {tracker.recent_success_rate:.0%})")
        
        # Auto-save every 5 records
        if tracker.total_attempts % 5 == 0:
            self.save()
    
    def get_best_tool_for_site(
        self,
        url: str,
        candidate_tools: List[str],
        min_attempts: int = 3
    ) -> Tuple[str, float]:
        """
        Get the best tool for a given site based on historical performance.
        
        Args:
            url: Site URL
            candidate_tools: List of tool names to consider
            min_attempts: Minimum attempts needed for reliable data
            
        Returns:
            Tuple of (best_tool_name, confidence_score)
        """
        site = self._extract_site(url)
        
        if site not in self.performance:
            # No data for this site, return first tool with 0 confidence
            return candidate_tools[0], 0.0
        
        site_tools = self.performance[site]
        
        # Score each candidate tool
        scored_tools = []
        for tool_name in candidate_tools:
            if tool_name not in site_tools:
                # No data for this tool on this site
                scored_tools.append((tool_name, 0.0))
                continue
            
            tracker = site_tools[tool_name]
            
            # If not enough attempts, lower confidence
            if tracker.total_attempts < min_attempts:
                confidence = tracker.reliability_score * (tracker.total_attempts / min_attempts)
            else:
                confidence = tracker.reliability_score
            
            scored_tools.append((tool_name, confidence))
        
        # Sort by confidence (descending)
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        
        best_tool, best_score = scored_tools[0]
        
        print(f"[LEARNING] Best tool for {site}: {best_tool} "
              f"(confidence: {best_score:.0%})")
        
        return best_tool, best_score
    
    def get_fallback_chain(
        self,
        url: str,
        all_tools: List[str]
    ) -> List[str]:
        """
        Get ordered list of tools to try (best to worst).
        
        Args:
            url: Site URL
            all_tools: All available tools
            
        Returns:
            Ordered list of tool names
        """
        site = self._extract_site(url)
        
        if site not in self.performance:
            # No data, return tools in original order
            return all_tools
        
        site_tools = self.performance[site]
        
        # Separate tools into: has_data and no_data
        tools_with_data = []
        tools_without_data = []
        
        for tool_name in all_tools:
            if tool_name in site_tools:
                tracker = site_tools[tool_name]
                tools_with_data.append((tool_name, tracker.reliability_score))
            else:
                tools_without_data.append(tool_name)
        
        # Sort tools with data by reliability
        tools_with_data.sort(key=lambda x: x[1], reverse=True)
        
        # Build final chain: best tools first, then untried tools
        chain = [tool for tool, _ in tools_with_data] + tools_without_data
        
        print(f"[LEARNING] Fallback chain for {site}: {' → '.join(chain)}")
        
        return chain
    
    def get_tool_stats(self, url: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get performance stats for a specific tool on a site."""
        site = self._extract_site(url)
        
        if site not in self.performance:
            return None
        
        if tool_name not in self.performance[site]:
            return None
        
        tracker = self.performance[site][tool_name]
        return tracker.to_dict()
    
    def get_site_stats(self, url: str) -> Dict[str, Dict[str, Any]]:
        """Get all tool performance stats for a site."""
        site = self._extract_site(url)
        
        if site not in self.performance:
            return {}
        
        return {
            tool_name: tracker.to_dict()
            for tool_name, tracker in self.performance[site].items()
        }
    
    def save(self):
        """Save performance data to cache."""
        try:
            data = {}
            
            for site, tools in self.performance.items():
                data[site] = {
                    tool_name: tracker.to_dict()
                    for tool_name, tracker in tools.items()
                }
            
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"[LEARNING] Saved performance data for {len(data)} sites")
            
        except Exception as e:
            print(f"[LEARNING] Error saving: {e}")
    
    def load(self):
        """Load performance data from cache."""
        try:
            if not self.cache_file.exists():
                print("[LEARNING] No existing performance data")
                return
            
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            for site, tools in data.items():
                for tool_name, tool_data in tools.items():
                    tracker = ToolPerformanceTracker.from_dict(tool_data)
                    self.performance[site][tool_name] = tracker
            
            print(f"[LEARNING] Loaded performance data for {len(data)} sites")
            
        except Exception as e:
            print(f"[LEARNING] Error loading: {e}")
    
    def clear_site_data(self, url: str):
        """Clear performance data for a specific site."""
        site = self._extract_site(url)
        if site in self.performance:
            del self.performance[site]
            self.save()
            print(f"[LEARNING] Cleared data for {site}")
    
    def get_global_tool_ranking(self) -> List[Tuple[str, float]]:
        """Get global tool ranking across all sites."""
        tool_scores = defaultdict(list)
        
        for site, tools in self.performance.items():
            for tool_name, tracker in tools.items():
                tool_scores[tool_name].append(tracker.reliability_score)
        
        # Calculate average score per tool
        rankings = []
        for tool_name, scores in tool_scores.items():
            avg_score = sum(scores) / len(scores) if scores else 0.0
            rankings.append((tool_name, avg_score))
        
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings


# Global instance
_learning_manager = None

def get_learning_manager() -> LearningManager:
    """Get global learning manager instance."""
    global _learning_manager
    if _learning_manager is None:
        _learning_manager = LearningManager()
    return _learning_manager
