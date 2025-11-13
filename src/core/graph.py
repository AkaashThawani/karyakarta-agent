"""
LangGraph Workflow - Modular agent workflow definition

Extracts the LangGraph workflow from agent_logic.py into a reusable module.
Provides clean separation between workflow definition and execution.

Uses LangGraph's built-in features:
- StateGraph for workflow definition
- ToolNode for tool execution
- Checkpointing for conversation memory

For LangGraph docs: https://langchain-ai.github.io/langgraph/
"""

from typing import List, Callable, Any, Optional
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver


def create_workflow(
    tools: List[Any],
    model_with_tools: Any,
    checkpointer: BaseCheckpointSaver,
    logger_callback: Optional[Callable[[str, str], None]] = None
):
    """
    Create a LangGraph workflow for agent reasoning.
    
    Args:
        tools: List of LangChain tools
        model_with_tools: LLM model with tools bound
        checkpointer: Memory checkpointer for conversation persistence
        logger_callback: Optional callback for logging (signature: fn(message, type))
        
    Returns:
        Compiled LangGraph application ready for execution
        
    Usage:
        from src.core.graph import create_workflow
        from src.services.llm_service import LLMService
        from src.core.memory import get_memory_service
        
        llm_service = LLMService(settings)
        memory = get_memory_service()
        
        model = llm_service.get_model_with_tools(tools)
        app = create_workflow(
            tools=tools,
            model_with_tools=model,
            checkpointer=memory.get_checkpointer(),
            logger_callback=lambda msg, type: print(f"{type}: {msg}")
        )
        
        # Execute
        config = {"configurable": {"thread_id": "session-123"}}
        result = app.invoke({"messages": [HumanMessage(content="Hello")]}, config=config)
    """
    
    def should_continue(state: MessagesState):
        """
        Decides whether to continue the loop or end.
        
        If the last message has tool calls, continue to tools node.
        Otherwise, end the workflow.
        """
        messages = state['messages']
        last_message = messages[-1]
        
        # AIMessage with tool_calls means agent wants to use tools
        if isinstance(last_message, AIMessage) and last_message.tool_calls:  # type: ignore
            return "continue"
        else:
            return "end"
    
    def call_model(state: MessagesState):
        """
        Agent node - invokes the LLM to decide the next action.
        
        The model analyzes the conversation and decides whether to:
        - Call a tool (returns AIMessage with tool_calls)
        - Provide final answer (returns AIMessage without tool_calls)
        """
        if logger_callback:
            logger_callback("Agent is analyzing the task...", "thinking")
        
        messages = state['messages']
        response = model_with_tools.invoke(messages)
        
        # Return new messages to add to state
        return {"messages": [response]}
    
    # Create the workflow graph
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges from agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",  # If agent calls tools, go to tools node
            "end": END,           # If agent provides answer, end workflow
        },
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile with checkpointer for memory persistence
    return workflow.compile(checkpointer=checkpointer)
