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

# --- Initialize services and tools ---
logger = LoggingService(settings.logging_url)
llm_service = LLMService(settings)

# Tools will be initialized per-session in run_agent_task
# to provide proper session_id for scraper and chunk reader
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
    
    # Convert to LangChain tools for use with LangGraph
    return [
        search_tool.as_langchain_tool(),
        scraper_tool.as_langchain_tool(),
        calculator_tool.as_langchain_tool(),
        extractor_tool.as_langchain_tool(),
        chunk_reader_tool.as_langchain_tool(),
        list_tools_tool.as_langchain_tool(),
    ]


# Initialize memory service for conversation persistence
memory_service = get_memory_service("data/conversations.db")

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
    
    # DEBUG: Log model response
    print(f"[DEBUG AGENT] Model response type: {type(response)}")
    if hasattr(response, 'content'):
        print(f"[DEBUG AGENT] Response content: {response.content[:200] if response.content else 'None'}...")
    if hasattr(response, 'tool_calls'):
        print(f"[DEBUG AGENT] Tool calls: {response.tool_calls}")
        if response.tool_calls:
            for tc in response.tool_calls:
                print(f"[DEBUG AGENT]   - Tool: {tc.get('name', 'unknown')}, Args: {tc.get('args', {})}")
    
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}

# --- This function is called by FastAPI ---
def run_agent_task(prompt: str, message_id: str, session_id: str = "default"):
    """Initializes and runs the LangGraph agent with message tracking."""
    global model  # Make model accessible within this function

    print(f"[Agent] Starting task with message ID: {message_id}, session ID: {session_id}")
    
    logger.status("Initializing AI agent...", message_id)

    # Create tools for this specific session
    tools = create_tools_for_session(session_id)
    
    # DEBUG: Log tool registration
    print("\n" + "="*70)
    print("🔧 TOOL REGISTRATION DEBUG")
    print("="*70)
    for i, lc_tool in enumerate(tools, 1):
        print(f"{i}. {lc_tool.name}")
        print(f"   Description: {lc_tool.description[:100] if lc_tool.description else 'N/A'}...")
        if hasattr(lc_tool, 'args_schema') and lc_tool.args_schema:
            try:
                schema = lc_tool.args_schema.schema()
                params = schema.get('properties', {})
                print(f"   Parameters: {list(params.keys())}")
            except:
                print(f"   Parameters: N/A")
        print()
    print(f"✅ Total tools registered: {len(tools)}")
    print("="*70 + "\n")

    # Get LLM model with tools bound - using LLM service
    model = llm_service.get_model_with_tools(tools)  # type: ignore
    
    # Create tool node
    tool_node = ToolNode(tools)

    # Define the graph
    workflow = StateGraph(MessagesState)
    
    # Define the two nodes we will cycle between
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    # Set the entrypoint as `agent`
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph with memory checkpointer for conversation persistence
    checkpointer = memory_service.get_checkpointer()
    app = workflow.compile(checkpointer=checkpointer)

    logger.status("Agent initialized successfully", message_id)
    logger.thinking("Starting task execution...", message_id)
    
    try:
        # Get session configuration for memory persistence
        session_config = memory_service.get_session_config(session_id)
        
        # Stream the graph execution with session memory
        final_answer = None
        response_sent = False  # Flag to prevent duplicate responses
        
        for s in app.stream({"messages": [HumanMessage(content=prompt)]}, config=session_config):  # type: ignore
            if "agent" in s:
                print(s)  # You'll see the agent's decisions in the Python terminal
                
                # Skip processing if we've already sent the response
                if response_sent:
                    continue
                    
                # Check if this is the final response (no tool calls)
                messages = s['agent']['messages']
                if messages:
                    last_message = messages[-1]
                    if isinstance(last_message, AIMessage):
                        # Check if there are no tool calls - this means it's the final answer
                        tool_calls = getattr(last_message, 'tool_calls', None)
                        if not tool_calls or len(tool_calls) == 0:
                            if hasattr(last_message, 'content') and last_message.content:
                                final_answer = str(last_message.content)
                                logger.status("Task completed successfully", message_id)
                                logger.response(final_answer, message_id)
                                response_sent = True  # Mark as sent to prevent duplicates
                                break  # Exit loop immediately to prevent any duplicate processing
                                
            if "tools" in s:
                print(s)  # You'll see the tool outputs
        
        # Return the final answer
        if final_answer:
            return final_answer
        
        error_msg = "Agent finished but no final answer found."
        logger.status(error_msg, message_id)
        return "No response generated"
        
    except Exception as e:
        error_msg = f"An error occurred during agent execution: {e}"
        logger.error(error_msg, message_id)
        return f"Error: {e}"
