"""
Fallback Manager - Intelligent Tool Fallback Chain

Manages tool fallback chains with learning integration.
Tries multiple tools in order of predicted success.

Architecture:
- Uses LearningManager for intelligent ordering
- Tries tools in order of reliability
- Records results for continuous learning
- Provides detailed failure context
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from src.tools.learning_manager import get_learning_manager
import time


class ToolFallbackChain:
    """
    Manages execution of tools with intelligent fallback.
    """
    
    # Define tool hierarchies for different task types
    TOOL_HIERARCHIES = {
        "browser_automation": [
            "playwright_execute",  # Primary: Full Playwright power
            "browse_advanced",     # Fallback 1: Simpler browser tools
            "browse_forms",        # Fallback 2: Form-specific tools
            "scraper"              # Fallback 3: Basic HTTP scraping
        ],
        "data_extraction": [
            "chart_extractor",     # Primary: Structured extraction
            "extract_advanced",    # Fallback 1: Advanced extractors
            "extract_structured",  # Fallback 2: Structured extractors
            "extractor"            # Fallback 3: Basic extractor
        ],
        "web_scraping": [
            "playwright_execute",  # Primary: Browser-based
            "browse_advanced",     # Fallback 1: Advanced browsing
            "scraper"              # Fallback 2: HTTP scraping
        ],
        "search": [
            "google_search"        # Only tool for search
        ]
    }
    
    def __init__(self):
        self.learning_manager = get_learning_manager()
    
    def execute_with_fallback(
        self,
        task_type: str,
        url: str,
        tool_executor: Callable[[str, Dict[str, Any]], Any],
        task_params: Dict[str, Any],
        max_attempts: Optional[int] = None
    ) -> Tuple[bool, Any, str]:
        """
        Execute a task with intelligent fallback chain.
        
        Args:
            task_type: Type of task (browser_automation, data_extraction, etc.)
            url: Target URL
            tool_executor: Function to execute tool (takes tool_name, params)
            task_params: Parameters for the task
            max_attempts: Maximum number of tools to try (None = try all)
            
        Returns:
            Tuple of (success, result, tool_used)
        """
        # Get tools for this task type
        if task_type not in self.TOOL_HIERARCHIES:
            print(f"[FALLBACK] Unknown task type: {task_type}")
            return False, None, ""
        
        available_tools = self.TOOL_HIERARCHIES[task_type]
        
        # Get intelligent fallback chain from learning manager
        ordered_tools = self.learning_manager.get_fallback_chain(url, available_tools)
        
        # Limit attempts if specified
        if max_attempts:
            ordered_tools = ordered_tools[:max_attempts]
        
        print(f"[FALLBACK] Executing {task_type} on {url}")
        print(f"[FALLBACK] Will try {len(ordered_tools)} tool(s): {' → '.join(ordered_tools)}")
        
        last_error = None
        
        # Try each tool in order
        for i, tool_name in enumerate(ordered_tools, 1):
            print(f"\n[FALLBACK] Attempt {i}/{len(ordered_tools)}: Trying {tool_name}...")
            
            start_time = time.time()
            
            try:
                # Execute tool
                result = tool_executor(tool_name, task_params)
                
                response_time = time.time() - start_time
                
                # Check if result indicates success
                success = self._is_successful_result(result)
                
                # Record result in learning manager
                self.learning_manager.record_tool_execution(
                    url=url,
                    tool_name=tool_name,
                    success=success,
                    response_time=response_time
                )
                
                if success:
                    print(f"[FALLBACK] ✅ {tool_name} succeeded! (took {response_time:.2f}s)")
                    return True, result, tool_name
                else:
                    print(f"[FALLBACK] ⚠️ {tool_name} returned unsuccessful result")
                    last_error = f"{tool_name} returned unsuccessful result"
                    continue
                    
            except Exception as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                print(f"[FALLBACK] ❌ {tool_name} failed: {error_msg[:100]}")
                
                # Record failure
                self.learning_manager.record_tool_execution(
                    url=url,
                    tool_name=tool_name,
                    success=False,
                    response_time=response_time
                )
                
                last_error = error_msg
                continue
        
        # All tools failed
        print(f"\n[FALLBACK] ❌ All {len(ordered_tools)} tools failed")
        print(f"[FALLBACK] Last error: {last_error}")
        
        return False, last_error, ""
    
    def _is_successful_result(self, result: Any) -> bool:
        """
        Determine if a tool result indicates success.
        
        Args:
            result: Tool execution result
            
        Returns:
            True if result indicates success
        """
        # Handle None
        if result is None:
            return False
        
        # Handle ToolResult objects
        if hasattr(result, 'success'):
            return result.success
        
        # Handle dictionaries
        if isinstance(result, dict):
            if 'success' in result:
                return result['success']
            if 'error' in result:
                return False
            # Non-empty dict considered success
            return len(result) > 0
        
        # Handle lists (extracted data)
        if isinstance(result, list):
            return len(result) > 0
        
        # Handle strings
        if isinstance(result, str):
            return len(result) > 0 and 'error' not in result.lower()
        
        # Other types considered success if truthy
        return bool(result)
    
    def get_recommended_tool(self, task_type: str, url: str) -> str:
        """
        Get the recommended tool for a task without executing.
        
        Args:
            task_type: Type of task
            url: Target URL
            
        Returns:
            Recommended tool name
        """
        if task_type not in self.TOOL_HIERARCHIES:
            return ""
        
        available_tools = self.TOOL_HIERARCHIES[task_type]
        best_tool, confidence = self.learning_manager.get_best_tool_for_site(
            url, available_tools
        )
        
        return best_tool
    
    def get_tool_stats_for_site(self, url: str) -> Dict[str, Dict[str, Any]]:
        """
        Get performance stats for all tools on a site.
        
        Args:
            url: Site URL
            
        Returns:
            Dictionary of tool stats
        """
        return self.learning_manager.get_site_stats(url)


# Global instance
_fallback_manager = None

def get_fallback_manager() -> ToolFallbackChain:
    """Get global fallback manager instance."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = ToolFallbackChain()
    return _fallback_manager


# Decorator for fallback-enabled tools
def with_fallback(task_type: str):
    """
    Decorator to add fallback capability to tool methods.
    
    Usage:
        @with_fallback("browser_automation")
        def execute_browser_task(url, params):
            # Implementation
            pass
    """
    def decorator(func):
        def wrapper(url: str, params: Dict[str, Any], **kwargs):
            fallback_manager = get_fallback_manager()
            
            def executor(tool_name: str, tool_params: Dict[str, Any]):
                # Add tool_name to params
                tool_params_with_name = {**tool_params, "tool": tool_name}
                return func(url, tool_params_with_name, **kwargs)
            
            success, result, tool_used = fallback_manager.execute_with_fallback(
                task_type=task_type,
                url=url,
                tool_executor=executor,
                task_params=params
            )
            
            return result
        
        return wrapper
    return decorator
