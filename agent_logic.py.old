# agent_logic.py
"""
Agent Logic - Refactored to use modular architecture

Uses new tool classes, LLM service, and centralized configuration.
Clean separation of concerns following SOLID principles.
"""

import operator
from typing import TypedDict, Annotated, List
from dotenv import load_dotenv

# --- LangChain & LangGraph Imports ---
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode

# --- Import our modular components ---
from src.core.config import settings
from src.core.agent import AgentManager
from src.services.logging_service import LoggingService
from src.services.llm_service import LLMService
from src.core.memory import get_memory_service
from src.tools.search import SearchTool
from src.tools.scraper import ScraperTool
from src.tools.calculator import CalculatorTool
from src.tools.extractor import ExtractorTool
from src.tools.list_tools import ListToolsTool
from src.tools.chunk_reader import GetNextChunkTool

load_dotenv()

# --- Initialize services ---
logger = LoggingService(settings.logging_url)
llm_service = LLMService(settings)
memory_service = get_memory_service("data/conversations.db")

# Global AgentManager instance (initialized once)
_agent_manager = None

def get_agent_manager():
    """Get or create the global AgentManager instance."""
    global _agent_manager
    if _agent_manager is None:
        # Create tools for global use
        tools = create_tools_for_session("global")
        _agent_manager = AgentManager(
            llm_service=llm_service,
            memory_service=memory_service,
            logging_service=logger,
            tools=tools
        )
        print("[AgentManager] Global instance created")
    return _agent_manager

def create_tools_for_session(session_id: str):
    """Create tools for a specific session."""
    # Initialize tools with logger and settings
    search_tool = SearchTool(logger)
    scraper_tool = ScraperTool(session_id, logger, settings)
    calculator_tool = CalculatorTool(logger)
    extractor_tool = ExtractorTool(logger)
    chunk_reader_tool = GetNextChunkTool(session_id, logger)
    
    # Create list of base tools for the list_tools meta-tool
    base_tools = [search_tool, scraper_tool, calculator_tool, extractor_tool, chunk_reader_tool]
    
    # Initialize list_tools meta-tool with the base tools
    list_tools_tool = ListToolsTool(base_tools, logger)
    
    # Return BaseTool instances (AgentManager will convert them to LangChain tools)
    return base_tools + [list_tools_tool]



# --- LangGraph Agent Implementation ---

# Define the function that determines whether to continue or not
def should_continue(state: MessagesState):
    """Decides whether to continue the loop or end."""
    messages = state['messages']
    last_message = messages[-1]
    # If there are no tool calls, then we finish
    # AIMessage has tool_calls, other message types don't
    if isinstance(last_message, AIMessage) and last_message.tool_calls:  # type: ignore
        return "continue"
    else:
        return "end"

# Define the function that calls the model
def call_model(state: MessagesState):
    """This node invokes the agent to decide the next action."""
    logger.thinking("Agent is analyzing the task...")
    messages = state['messages']
    
    # DEBUG: Log what's being sent to the model
    print(f"\n[DEBUG AGENT] Calling model with {len(messages)} messages")
    print(f"[DEBUG AGENT] Last message: {messages[-1].content if messages else 'None'}[:100]...")
    
    response = model.invoke(messages)  # type: ignore
    
    # ============ ENHANCED DEBUG LOGGING ============
    print(f"\n{'='*80}")
    print(f"🤖 MODEL RESPONSE DEBUG")
    print(f"{'='*80}")
    print(f"Response Type: {type(response)}")
    
    # Log content
    if hasattr(response, 'content'):
        content_preview = response.content[:200] if response.content else 'EMPTY/None'
        print(f"Content Length: {len(response.content) if response.content else 0}")
        print(f"Content Preview: {content_preview}")
    
    # Log tool calls
    if hasattr(response, 'tool_calls'):
        print(f"Tool Calls Count: {len(response.tool_calls) if response.tool_calls else 0}")
        if response.tool_calls:
            for i, tc in enumerate(response.tool_calls, 1):
                print(f"  Tool {i}: {tc.get('name', 'unknown')}")
                print(f"    Args: {tc.get('args', {})}")
    
    # Log metadata (safety, tokens, etc.)
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        print(f"\n📊 Response Metadata:")
        print(f"  Model: {metadata.get('model_name', 'N/A')}")
        print(f"  Finish Reason: {metadata.get('finish_reason', 'N/A')}")
        
        # Safety ratings
        if 'safety_ratings' in metadata:
            print(f"  Safety Ratings: {metadata['safety_ratings']}")
        
        # Prompt feedback (for blocking)
        if 'prompt_feedback' in metadata:
            feedback = metadata['prompt_feedback']
            print(f"  Prompt Feedback:")
            print(f"    Block Reason: {feedback.get('block_reason', 'N/A')}")
            print(f"    Safety Ratings: {feedback.get('safety_ratings', [])}")
    
    # Log token usage
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        print(f"\n🎯 Token Usage:")
        print(f"  Input Tokens: {usage.get('input_tokens', 0)}")
        print(f"  Output Tokens: {usage.get('output_tokens', 0)} {'⚠️ ZERO!' if usage.get('output_tokens', 0) == 0 else ''}")
        print(f"  Total Tokens: {usage.get('total_tokens', 0)}")
    
    print(f"{'='*80}\n")
    
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}

# --- This function is called by FastAPI ---
def run_agent_task(prompt: str, message_id: str, session_id: str = "default"):
    """
    Execute agent task using the global AgentManager.
    
    This is now a thin wrapper that delegates to AgentManager,
    which maintains agent state and prevents reinitialization.
    """
    print(f"[AgentLogic] Delegating to AgentManager - Session: {session_id}, Message: {message_id}")
    
    try:
        # Get the global AgentManager instance
        manager = get_agent_manager()
        
        # Delegate execution to AgentManager
        result = manager.execute_task(
            prompt=prompt,
            message_id=message_id,
            session_id=session_id
        )
        
        return result
        
    except Exception as e:
        error_msg = f"An error occurred during agent execution: {e}"
        logger.error(error_msg, message_id)
        print(f"[AgentLogic] Error: {e}")
        return f"Error: {e}"
