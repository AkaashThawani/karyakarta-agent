"""
Executor Agent - Tool Execution

Responsible for executing tools and handling results.
Generic executor that can work with any tool.
"""

from typing import List, Dict, Any, Optional
from src.agents.base_agent import (
    BaseAgent, AgentTask, AgentResult, AgentMessage,
    MessageType, AgentStatus
)
from src.tools.base import BaseTool, ToolResult
from src.prompts import get_executor_agent_prompt, get_executor_agent_general_prompt
import time


class ExecutorAgent(BaseAgent):
    """
    Generic agent that executes tools.
    
    The Executor Agent is responsible for:
    - Executing tool calls
    - Handling errors and retries
    - Formatting results consistently
    - Managing tool timeouts
    
    Example:
        from src.tools import SearchTool, ScraperTool
        
        executor = ExecutorAgent(
            agent_id="executor_1",
            tools=[search_tool, scraper_tool]
        )
        
        task = AgentTask(
            task_type="search",
            description="Search for Python tutorials",
            parameters={"query": "Python tutorials"}
        )
        
        result = executor.execute(task)
    """
    
    def __init__(
        self,
        agent_id: str,
        tools: List[BaseTool],
        logger: Optional[Any] = None,
        max_retries: int = 3
    ):
        """
        Initialize Executor Agent.
        
        Args:
            agent_id: Unique identifier for this agent
            tools: List of tools this agent can execute
            logger: Optional logging service
            max_retries: Maximum retry attempts for failed executions
        """
        # Get tool names for capabilities
        capabilities = [tool.name for tool in tools]
        
        super().__init__(
            agent_id=agent_id,
            agent_type="executor",
            capabilities=capabilities,
            logger=logger
        )
        
        # Store tools in dictionary for quick lookup
        self.tools: Dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self.max_retries = max_retries
        self.execution_stats: Dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "by_tool": {}
        }
    
    def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Execute a tool-based task.
        
        Args:
            task: Task to execute
            context: Optional execution context
            
        Returns:
            AgentResult with tool execution results
        """
        start_time = time.time()
        self.state.update_status(AgentStatus.EXECUTING)
        # print(f"[EXECUTOR] Starting execution of task: {task.task_type}")
        # print(f"[EXECUTOR] Task parameters: {task.parameters}")
        self.log(f"Executor agent executing task: {task.task_type}")
        
        try:
            # Find appropriate tool
            tool = self._find_tool_for_task(task)
            
            if not tool:
                print(f"[EXECUTOR] ✗ No tool found for: {task.task_type}")
                raise ValueError(f"No tool found for task type: {task.task_type}")
            
            # Execute tool with retry logic
            tool_result = self._execute_with_retry(tool, task.parameters)
            print(f"[EXECUTOR] ✓ {tool.name}: Success={tool_result.success}, Type={type(tool_result.data).__name__}")
            
            # Update stats
            self._update_stats(tool.name, tool_result.success)
            
            execution_time = time.time() - start_time
            self.state.update_status(AgentStatus.COMPLETED)
            
            if tool_result.success:
                # FIX 5: Evaluate task completeness
                completeness = self._evaluate_completeness(task, tool_result, context)
                
                return AgentResult.success_result(
                    data=tool_result.data,
                    agent_id=self.agent_id,
                    execution_time=execution_time,
                    metadata={
                        "tool": tool.name,
                        "tool_metadata": tool_result.metadata,
                        "complete": completeness["complete"],
                        "completeness_reason": completeness.get("reason"),
                        "suggested_action": completeness.get("next_action"),
                        "coverage": completeness.get("coverage", "100%")
                    }
                )
            else:
                return AgentResult.error_result(
                    error=tool_result.error or "Tool execution failed",
                    agent_id=self.agent_id,
                    execution_time=execution_time,
                    metadata={"tool": tool.name}
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.state.update_status(AgentStatus.ERROR, str(e))
            self.log(f"Error in executor agent: {e}", level="error")
            
            return AgentResult.error_result(
                error=str(e),
                agent_id=self.agent_id,
                execution_time=execution_time
            )
    
    def can_handle(self, task: AgentTask) -> bool:
        """
        Check if this executor can handle the task.
        
        Args:
            task: Task to check
            
        Returns:
            True if executor has the required tool
        """
        return task.task_type in self.tools or task.task_type in self.state.capabilities
    
    def _find_tool_for_task(self, task: AgentTask) -> Optional[BaseTool]:
        """
        Find appropriate tool for task.
        
        Args:
            task: Task to find tool for
            
        Returns:
            Tool instance or None
        """
        # Direct match by task type
        if task.task_type in self.tools:
            return self.tools[task.task_type]
        
        # Try to find by capability
        for tool_name, tool in self.tools.items():
            if task.task_type in tool_name or tool_name in task.task_type:
                return tool
        
        return None
    
    def _execute_with_retry(
        self,
        tool: BaseTool,
        parameters: Dict[str, Any]
    ) -> ToolResult:
        """
        Execute tool with retry logic.
        Handles both synchronous and asynchronous tools.
        
        Args:
            tool: Tool to execute
            parameters: Tool parameters
            
        Returns:
            ToolResult from tool execution
        """
        import asyncio
        import inspect
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                self.log(f"Attempt {attempt + 1}/{self.max_retries} for {tool.name}")
                
                # Check if tool.execute returns a coroutine (async)
                result = tool.execute(**parameters)
                
                # If result is a coroutine, await it
                if inspect.iscoroutine(result):
                    print(f"[EXECUTOR] Tool {tool.name} is async, awaiting...")
                    try:
                        # Try to use existing event loop
                        loop = asyncio.get_running_loop()
                        # Loop is running, we're in async context - shouldn't happen
                        # but if it does, schedule the coroutine
                        future = asyncio.run_coroutine_threadsafe(result, loop)
                        result = future.result()
                    except RuntimeError:
                        # No running loop, create one with asyncio.run
                        result = asyncio.run(result)
                    print(f"[EXECUTOR] Async tool completed")
                
                if result.success:
                    if attempt > 0:
                        self.log(f"Success on retry attempt {attempt + 1}")
                    return result
                else:
                    last_error = result.error
                    # Don't log errors during retries - only final failure
                    # self.log(f"Tool execution failed: {result.error}", level="error")
                    
                    # Don't retry if it's a validation error
                    if "validation" in str(result.error).lower():
                        return result
                    
            except Exception as e:
                last_error = str(e)
                # Don't log errors during retries - only log final failure
                # self.log(f"Exception during tool execution: {e}", level="error")
                
                # Don't retry on certain exceptions
                if isinstance(e, (ValueError, TypeError)):
                    break
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
        
        # All retries failed - PRINT THE ERROR!
        print(f"[EXECUTOR] ❌ Tool {tool.name} failed after {self.max_retries} attempts")
        print(f"[EXECUTOR] ❌ Last error: {last_error}")
        
        return ToolResult(
            success=False,
            error=f"Tool execution failed after {self.max_retries} attempts. Last error: {last_error}",
            metadata={"retries": self.max_retries}
        )
    
    def _update_stats(self, tool_name: str, success: bool) -> None:
        """
        Update execution statistics.
        
        Args:
            tool_name: Name of tool executed
            success: Whether execution succeeded
        """
        self.execution_stats["total_executions"] += 1
        
        if success:
            self.execution_stats["successful_executions"] += 1
        else:
            self.execution_stats["failed_executions"] += 1
        
        # Update per-tool stats
        if tool_name not in self.execution_stats["by_tool"]:
            self.execution_stats["by_tool"][tool_name] = {
                "total": 0,
                "success": 0,
                "failed": 0
            }
        
        self.execution_stats["by_tool"][tool_name]["total"] += 1
        if success:
            self.execution_stats["by_tool"][tool_name]["success"] += 1
        else:
            self.execution_stats["by_tool"][tool_name]["failed"] += 1
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())
    
    def _evaluate_completeness(
        self,
        task: AgentTask,
        tool_result: ToolResult,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate if the task was completed fully or needs more work.
        
        Args:
            task: Original task
            tool_result: Tool execution result
            context: Execution context
            
        Returns:
            Dict with completeness info: {
                "complete": bool,
                "reason": str (if incomplete),
                "next_action": str (if incomplete),
                "coverage": str (e.g., "70%")
            }
        """
        completeness = {
            "complete": True,
            "coverage": "100%"
        }
        
        try:
            # Check if task had specific requirements
            task_desc = task.description.lower()
            result_data = str(tool_result.data).lower()
            
            # Check for quantity requirements (e.g., "top 10", "5 items")
            import re
            quantity_match = re.search(r'(top|find|get|list)\s+(\d+)', task_desc)
            if quantity_match:
                requested_count = int(quantity_match.group(2))
                
                # Try to count items in result
                # Simple heuristic: count lines, list items, or numbered entries
                result_lines = tool_result.data.split('\n') if isinstance(tool_result.data, str) else []
                numbered_items = len(re.findall(r'^\d+[\.\)]\s+', tool_result.data, re.MULTILINE)) if isinstance(tool_result.data, str) else 0
                list_items = len(re.findall(r'^[-\*]\s+', tool_result.data, re.MULTILINE)) if isinstance(tool_result.data, str) else 0
                
                found_count = max(numbered_items, list_items, len([l for l in result_lines if l.strip()]))
                
                if found_count < requested_count:
                    coverage = int((found_count / requested_count) * 100)
                    completeness = {
                        "complete": False,
                        "reason": f"Found {found_count}/{requested_count} items",
                        "next_action": "search_more_sources",
                        "coverage": f"{coverage}%"
                    }
                    self.log(f"Task incomplete: {completeness['reason']}")
            
            # Check for specific fields requested (e.g., "with price and specs")
            required_fields = []
            if 'price' in task_desc and 'price' not in result_data and '$' not in result_data:
                required_fields.append('price')
            if 'spec' in task_desc and 'spec' not in result_data:
                required_fields.append('specifications')
            if 'rating' in task_desc and 'rating' not in result_data and '⭐' not in result_data:
                required_fields.append('rating')
            
            if required_fields:
                completeness = {
                    "complete": False,
                    "reason": f"Missing required fields: {', '.join(required_fields)}",
                    "next_action": "extract_more_details",
                    "coverage": "75%"
                }
                self.log(f"Task incomplete: {completeness['reason']}")
            
            # Check result size - if very short, might be incomplete
            if isinstance(tool_result.data, str) and len(tool_result.data.strip()) < 50:
                if 'find' in task_desc or 'search' in task_desc:
                    completeness = {
                        "complete": False,
                        "reason": "Result too brief for search query",
                        "next_action": "search_alternate_sources",
                        "coverage": "50%"
                    }
                    self.log(f"Task incomplete: {completeness['reason']}")
            
        except Exception as e:
            # If evaluation fails, assume complete to avoid blocking
            self.log(f"Completeness evaluation failed: {e}", level="warning")
        
        return completeness
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get specific tool by name.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool instance or None
        """
        return self.tools.get(tool_name)
    
    def add_tool(self, tool: BaseTool) -> None:
        """
        Add a new tool to this executor.
        
        Args:
            tool: Tool to add
        """
        self.tools[tool.name] = tool
        self.state.add_capability(tool.name)
        self.log(f"Added tool: {tool.name}")
    
    def remove_tool(self, tool_name: str) -> bool:
        """
        Remove a tool from this executor.
        
        Args:
            tool_name: Name of tool to remove
            
        Returns:
            True if removed, False if not found
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.log(f"Removed tool: {tool_name}")
            return True
        return False
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.
        
        Returns:
            Dictionary of execution stats
        """
        stats = self.execution_stats.copy()
        
        # Calculate success rate
        total = stats["total_executions"]
        if total > 0:
            stats["success_rate"] = (stats["successful_executions"] / total) * 100
        else:
            stats["success_rate"] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "by_tool": {}
        }
    
    def execute_tool_directly(
        self,
        tool_name: str,
        **parameters
    ) -> ToolResult:
        """
        Execute a specific tool directly.
        
        Args:
            tool_name: Name of tool to execute
            **parameters: Tool parameters
            
        Returns:
            ToolResult from tool execution
        """
        tool = self.tools.get(tool_name)
        
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )
        
        return self._execute_with_retry(tool, parameters)
