"""
Agent Logic - Multi-Agent System Integration

Uses new AgentManager or MultiAgentManager based on configuration.
Provides backward-compatible interface for API routes.
"""

from typing import Dict, Any
from dotenv import load_dotenv

# Import modular components
from src.core.config import settings
from src.core.agent import AgentManager, MultiAgentManager
from src.services.logging_service import LoggingService
from src.services.llm_service import LLMService
from src.core.memory import get_memory_service
from src.routing import RoutingStrategy

# Import tools that actually exist
from src.tools.search import SearchTool
from src.tools.calculator import CalculatorTool
from src.tools.chunk_reader import GetNextChunkTool
from src.tools.analysis_tools import (
    AnalyzeSentimentTool, SummarizeContentTool, CompareDataTool, ValidateDataTool
)
from src.tools.playwright_universal import UniversalPlaywrightTool
from src.tools.chart_extractor_tool import ChartExtractorTool
from src.tools.content_extractor_tool import ContentExtractorTool
from src.tools.interactive_element_extractor_tool import InteractiveElementExtractorTool
from src.tools.api_call import APICallTool

load_dotenv()

# Initialize services
logger = LoggingService(settings.logging_url)
llm_service = LLMService(settings)
memory_service = get_memory_service("data/conversations.db")

# Global manager instance
_agent_manager = None

# Global task tracking for cancellation
active_tasks: Dict[str, Any] = {}
cancellation_flags: Dict[str, bool] = {}

# Configuration: Set to True to enable multi-agent system
USE_MULTI_AGENT_SYSTEM = True  # Change to False for classic mode


def get_agent_manager():
    """
    Get or create the global AgentManager/MultiAgentManager instance.
    
    Returns:
        AgentManager or MultiAgentManager instance
    """
    global _agent_manager
    if _agent_manager is None:
        # Create tools
        tools = create_tools_for_session("global")
        
        if USE_MULTI_AGENT_SYSTEM:
            # Use multi-agent system with intelligent routing
            _agent_manager = MultiAgentManager(
                llm_service=llm_service,
                memory_service=memory_service,
                logging_service=logger,
                tools=tools,
                enable_routing=True,
                routing_strategy=RoutingStrategy.BALANCED
            )
            print("[AgentLogic] Multi-Agent system initialized with intelligent routing")
        else:
            # Use classic AgentManager
            _agent_manager = AgentManager(
                llm_service=llm_service,
                memory_service=memory_service,
                logging_service=logger,
                tools=tools
            )
            print("[AgentLogic] Classic AgentManager initialized")
    
    return _agent_manager


def create_tools_for_session(session_id: str):
    """
    Create tools for a specific session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of tool instances
    """
    # Initialize base tools that exist
    search_tool = SearchTool(logger)
    calculator_tool = CalculatorTool(logger)
    chunk_reader_tool = GetNextChunkTool(session_id, logger)
    
    # Initialize analysis tools
    analyze_sentiment_tool = AnalyzeSentimentTool(session_id, logger, settings, llm_service)
    summarize_content_tool = SummarizeContentTool(session_id, logger, settings, llm_service)
    compare_data_tool = CompareDataTool(session_id, logger, settings)
    validate_data_tool = ValidateDataTool(session_id, logger, settings)
    
    # Initialize Universal Playwright Tool
    universal_playwright_tool = UniversalPlaywrightTool(session_id, logger, settings)

    # Initialize Content Extractor Tool (fast, clean content extraction)
    content_extractor_tool = ContentExtractorTool(logger)

    # Initialize Interactive Element Extractor Tool (task-aware element extraction)
    interactive_element_extractor_tool = InteractiveElementExtractorTool(logger)

    # Chart Extractor Tool disabled - replaced by ContentExtractor
    # chart_extractor_tool = ChartExtractorTool()

    # Initialize API Call Tool
    api_call_tool = APICallTool()
    
    # Create list of all tools
    all_tools = [
        # Base tools
        search_tool,
        calculator_tool,
        chunk_reader_tool,
        # Analysis tools
        analyze_sentiment_tool,
        summarize_content_tool,
        compare_data_tool,
        validate_data_tool,
        # Universal Playwright Tool (dynamic method execution)
        universal_playwright_tool,
        # Content Extractor Tool (fast, clean content extraction)
        content_extractor_tool,
        # Interactive Element Extractor Tool (task-aware element extraction)
        interactive_element_extractor_tool,
        # API Call Tool (HTTP requests for APIs)
        api_call_tool,
    ]
    
    # Return all tools
    return all_tools


def run_agent_task(prompt: str, message_id: str, session_id: str = "default"):
    """
    Execute agent task using AgentManager or MultiAgentManager.
    
    This function maintains backward compatibility with the API routes
    while supporting both classic and multi-agent execution modes.
    
    Args:
        prompt: User's input/question
        message_id: Unique message identifier
        session_id: Session identifier
        
    Returns:
        str: Agent's response
    """
    import asyncio
    import signal
    from concurrent.futures import ThreadPoolExecutor
    import threading
    
    print(f"[AgentLogic] Executing task - Session: {session_id}, Message: {message_id}")
    print(f"[AgentLogic] Mode: {'Multi-Agent' if USE_MULTI_AGENT_SYSTEM else 'Classic'}")
    
    # Initialize cancellation flag for this task
    cancellation_flags[message_id] = False
    
    # Increased timeout to 300 seconds (5 minutes) to prevent premature timeouts
    TASK_TIMEOUT = 300.0
    
    # Set up timeout and cancellation handling with proper cleanup
    async def execute_with_timeout():
        task = None
        executor = ThreadPoolExecutor(max_workers=1)
        
        try:
            # Get the global manager instance
            manager = get_agent_manager()
            
            # Create a proper asyncio task instead of using to_thread
            # This allows proper cancellation
            try:
                if isinstance(manager, MultiAgentManager):
                    # Use multi-agent execution
                    task = asyncio.create_task(
                        asyncio.to_thread(
                            manager.execute_task_multi_agent,
                            prompt=prompt,
                            message_id=message_id,
                            session_id=session_id,
                            use_reason_agent=True
                        )
                    )
                else:
                    # Use classic execution
                    task = asyncio.create_task(
                        asyncio.to_thread(
                            manager.execute_task,
                            prompt=prompt,
                            message_id=message_id,
                            session_id=session_id
                        )
                    )
                
                # Store task reference for cancellation
                active_tasks[message_id] = task
                
                # Wait for task with timeout
                result = await asyncio.wait_for(task, timeout=TASK_TIMEOUT)
                
                # Clean up task reference on completion
                if message_id in active_tasks:
                    del active_tasks[message_id]
                if message_id in cancellation_flags:
                    del cancellation_flags[message_id]
                
                print(f"[AgentLogic] Task completed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Task execution timeout after {TASK_TIMEOUT} seconds"
                logger.error(error_msg, message_id)
                logger.status(f"❌ {error_msg}")
                print(f"[AgentLogic] {error_msg}")
                
                # CRITICAL: Cancel the task to stop the thread
                if task and not task.done():
                    print(f"[AgentLogic] Cancelling running task...")
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=5.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        print(f"[AgentLogic] Task cancellation timed out or was cancelled")
                
                # Cleanup Playwright browsers for this session
                print(f"[AgentLogic] Cleaning up resources for session: {session_id}")
                try:
                    from src.tools.playwright_universal import UniversalPlaywrightTool
                    await UniversalPlaywrightTool.cleanup_session(session_id)
                except Exception as cleanup_error:
                    print(f"[AgentLogic] Cleanup error: {cleanup_error}")
                
                # Clean up tracking
                if message_id in active_tasks:
                    del active_tasks[message_id]
                if message_id in cancellation_flags:
                    del cancellation_flags[message_id]
                
                return f"Error: {error_msg}. The task took too long and was cancelled. Please try a simpler query or break it into smaller steps."
                
        except asyncio.CancelledError:
            print(f"[AgentLogic] Task cancelled by user")
            logger.status("❌ Task cancelled by user")
            
            # Cleanup on cancellation
            if task and not task.done():
                task.cancel()
            
            # Cleanup Playwright resources
            try:
                from src.tools.playwright_universal import UniversalPlaywrightTool
                await UniversalPlaywrightTool.cleanup_session(session_id)
            except Exception as cleanup_error:
                print(f"[AgentLogic] Cleanup error: {cleanup_error}")
            
            # Clean up tracking
            if message_id in active_tasks:
                del active_tasks[message_id]
            if message_id in cancellation_flags:
                del cancellation_flags[message_id]
            
            return "Task cancelled by user"
        except Exception as e:
            error_msg = f"An error occurred during agent execution: {e}"
            logger.error(error_msg, message_id)
            print(f"[AgentLogic] Error: {e}")
            
            # Cleanup on error
            if task and not task.done():
                task.cancel()
            
            # Clean up tracking
            if message_id in active_tasks:
                del active_tasks[message_id]
            if message_id in cancellation_flags:
                del cancellation_flags[message_id]
            
            return f"Error: {e}"
        finally:
            # Shutdown executor
            executor.shutdown(wait=False)
    
    # Run with asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(execute_with_timeout())
        return result
    except KeyboardInterrupt:
        print(f"[AgentLogic] Interrupted by user")
        return "Task interrupted by user"


# Utility functions for runtime configuration
def enable_multi_agent_mode():
    """Enable multi-agent system mode (requires restart)."""
    global USE_MULTI_AGENT_SYSTEM
    USE_MULTI_AGENT_SYSTEM = True
    print("[AgentLogic] Multi-agent mode enabled (restart required)")


def enable_classic_mode():
    """Enable classic AgentManager mode (requires restart)."""
    global USE_MULTI_AGENT_SYSTEM
    USE_MULTI_AGENT_SYSTEM = False
    print("[AgentLogic] Classic mode enabled (restart required)")


def get_current_mode():
    """Get current execution mode."""
    return "Multi-Agent" if USE_MULTI_AGENT_SYSTEM else "Classic"


def cancel_task(message_id: str = None) -> Dict[str, Any]:
    """
    Cancel running task(s).
    
    Args:
        message_id: The message ID of the task to cancel. If None or "all", cancels ALL active tasks.
        
    Returns:
        Dictionary with status and message
    """
    import asyncio
    
    # If no message_id provided, cancel ALL active tasks
    if message_id is None or message_id == "all":
        print(f"[AgentLogic] Cancellation requested for ALL active tasks")
        
        if not active_tasks:
            print(f"[AgentLogic] No active tasks to cancel")
            return {
                "status": "no_tasks",
                "message": "No active tasks to cancel"
            }
        
        # Cancel all tasks
        cancelled_count = 0
        task_ids = list(active_tasks.keys())
        
        for task_id in task_ids:
            # Set cancellation flag
            cancellation_flags[task_id] = True
            
            # Get the task
            task = active_tasks.get(task_id)
            
            if task and not task.done():
                # Cancel the asyncio task
                task.cancel()
                cancelled_count += 1
                print(f"[AgentLogic] Task {task_id} cancelled")
                
                # Log the cancellation
                logger.status(f"🛑 Task cancelled by user", task_id)
        
        print(f"[AgentLogic] Cancelled {cancelled_count} active task(s)")
        
        return {
            "status": "cancelled",
            "message": f"Cancelled {cancelled_count} active task(s)",
            "cancelled_count": cancelled_count
        }
    
    # Cancel specific task by message_id
    print(f"[AgentLogic] Cancellation requested for message: {message_id}")
    
    if message_id not in active_tasks:
        print(f"[AgentLogic] Task {message_id} not found in active tasks")
        return {
            "status": "not_found",
            "message": f"Task {message_id} not found or already completed"
        }
    
    # Set cancellation flag
    cancellation_flags[message_id] = True
    
    # Get the task
    task = active_tasks.get(message_id)
    
    if task and not task.done():
        # Cancel the asyncio task
        task.cancel()
        print(f"[AgentLogic] Task {message_id} cancellation initiated")
        
        # Log the cancellation
        logger.status(f"🛑 Task cancelled by user", message_id)
        
        return {
            "status": "cancelled",
            "message": f"Task {message_id} has been cancelled"
        }
    else:
        print(f"[AgentLogic] Task {message_id} already completed or not running")
        return {
            "status": "already_completed",
            "message": f"Task {message_id} has already completed"
        }
