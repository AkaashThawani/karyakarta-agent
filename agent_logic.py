"""
Agent Logic - Multi-Agent System Integration

Uses new AgentManager or MultiAgentManager based on configuration.
Provides backward-compatible interface for API routes.
"""

from dotenv import load_dotenv

# Import modular components
from src.core.config import settings
from src.core.agent import AgentManager, MultiAgentManager
from src.services.logging_service import LoggingService
from src.services.llm_service import LLMService
from src.core.memory import get_memory_service
from src.routing import RoutingStrategy

# Import tools
from src.tools.search import SearchTool
from src.tools.scraper import ScraperTool
from src.tools.calculator import CalculatorTool
from src.tools.extractor import ExtractorTool
from src.tools.list_tools import ListToolsTool
from src.tools.chunk_reader import GetNextChunkTool

# Import new advanced tools
from src.tools.extract_structured import ExtractStructuredTool
from src.tools.extract_advanced import (
    ExtractTableTool, ExtractLinksTool, ExtractImagesTool, ExtractTextBlocksTool
)
from src.tools.browse_advanced import (
    BrowseAndWaitTool, BrowseWithScrollTool, BrowseWithClickTool
)
from src.tools.browse_forms import (
    BrowseWithFormTool, BrowseWithAuthTool, BrowseMultiPageTool
)
from src.tools.analysis_tools import (
    AnalyzeSentimentTool, SummarizeContentTool, CompareDataTool, ValidateDataTool
)
from src.tools.playwright_universal import UniversalPlaywrightTool
from src.tools.chart_extractor_tool import ChartExtractorTool
from src.tools.api_call import APICallTool
from src.tools.excel_export import ExcelExportTool, CSVExportTool

load_dotenv()

# Initialize services
logger = LoggingService(settings.logging_url)
llm_service = LLMService(settings)
memory_service = get_memory_service("data/conversations.db")

# Global manager instance
_agent_manager = None

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
    # Initialize base tools
    search_tool = SearchTool(logger)
    scraper_tool = ScraperTool(session_id, logger, settings)
    calculator_tool = CalculatorTool(logger)
    extractor_tool = ExtractorTool(logger)
    chunk_reader_tool = GetNextChunkTool(session_id, logger)
    
    # Initialize extraction tools
    extract_structured_tool = ExtractStructuredTool(session_id, logger, settings)
    extract_table_tool = ExtractTableTool(session_id, logger, settings)
    extract_links_tool = ExtractLinksTool(session_id, logger, settings)
    extract_images_tool = ExtractImagesTool(session_id, logger, settings)
    extract_text_blocks_tool = ExtractTextBlocksTool(session_id, logger, settings)
    
    # Initialize advanced browsing tools
    browse_and_wait_tool = BrowseAndWaitTool(session_id, logger, settings)
    browse_with_scroll_tool = BrowseWithScrollTool(session_id, logger, settings)
    browse_with_click_tool = BrowseWithClickTool(session_id, logger, settings)
    
    # Initialize form and navigation tools
    browse_with_form_tool = BrowseWithFormTool(session_id, logger, settings)
    browse_with_auth_tool = BrowseWithAuthTool(session_id, logger, settings)
    browse_multi_page_tool = BrowseMultiPageTool(session_id, logger, settings)
    
    # Initialize analysis tools
    analyze_sentiment_tool = AnalyzeSentimentTool(session_id, logger, settings, llm_service)
    summarize_content_tool = SummarizeContentTool(session_id, logger, settings, llm_service)
    compare_data_tool = CompareDataTool(session_id, logger, settings)
    validate_data_tool = ValidateDataTool(session_id, logger, settings)
    
    # Initialize Universal Playwright Tool
    universal_playwright_tool = UniversalPlaywrightTool(session_id, logger, settings)
    
    # Initialize Chart Extractor Tool
    chart_extractor_tool = ChartExtractorTool()
    
    # Initialize API Call Tool
    api_call_tool = APICallTool()
    
    # Initialize Export Tools
    excel_export_tool = ExcelExportTool(session_id, logger)
    csv_export_tool = CSVExportTool(session_id, logger)
    
    # Create list of all tools
    all_tools = [
        # Base tools
        search_tool,
        scraper_tool,
        calculator_tool,
        extractor_tool,
        chunk_reader_tool,
        # Extraction tools
        extract_structured_tool,
        extract_table_tool,
        extract_links_tool,
        extract_images_tool,
        extract_text_blocks_tool,
        # Browsing tools
        browse_and_wait_tool,
        browse_with_scroll_tool,
        browse_with_click_tool,
        browse_with_form_tool,
        browse_with_auth_tool,
        browse_multi_page_tool,
        # Analysis tools
        analyze_sentiment_tool,
        summarize_content_tool,
        compare_data_tool,
        validate_data_tool,
        # Universal Playwright Tool (dynamic method execution)
        universal_playwright_tool,
        # Chart Extractor Tool (structured data extraction)
        chart_extractor_tool,
        # API Call Tool (HTTP requests for APIs)
        api_call_tool,
        # Export Tools (Excel/CSV export)
        excel_export_tool,
        csv_export_tool
    ]
    
    # Initialize list_tools meta-tool
    list_tools_tool = ListToolsTool(all_tools, logger)
    
    # Return all tools including meta-tool
    return all_tools + [list_tools_tool]


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
    
    print(f"[AgentLogic] Executing task - Session: {session_id}, Message: {message_id}")
    print(f"[AgentLogic] Mode: {'Multi-Agent' if USE_MULTI_AGENT_SYSTEM else 'Classic'}")
    
    # Set up timeout and cancellation handling
    async def execute_with_timeout():
        try:
            # Get the global manager instance
            manager = get_agent_manager()
            
            # Wrap execution in 120 second timeout
            try:
                if isinstance(manager, MultiAgentManager):
                    # Use multi-agent execution
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            manager.execute_task_multi_agent,
                            prompt=prompt,
                            message_id=message_id,
                            session_id=session_id,
                            use_reason_agent=True
                        ),
                        timeout=120.0
                    )
                else:
                    # Use classic execution
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            manager.execute_task,
                            prompt=prompt,
                            message_id=message_id,
                            session_id=session_id
                        ),
                        timeout=120.0
                    )
                
                print(f"[AgentLogic] Task completed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = "Task execution timeout after 120 seconds"
                logger.error(error_msg, message_id)
                logger.status(f"❌ {error_msg}")
                print(f"[AgentLogic] {error_msg}")
                return f"Error: {error_msg}"
                
        except asyncio.CancelledError:
            print(f"[AgentLogic] Task cancelled")
            logger.status("❌ Task cancelled by user")
            raise
        except Exception as e:
            error_msg = f"An error occurred during agent execution: {e}"
            logger.error(error_msg, message_id)
            print(f"[AgentLogic] Error: {e}")
            return f"Error: {e}"
    
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
