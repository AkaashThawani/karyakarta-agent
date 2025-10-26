"""
Agent Manager - Session-based agent lifecycle management

Manages agent instances with dependency injection pattern.
Provides clean interface for executing tasks with memory and logging.

Uses modular components:
- LLM Service for model management
- Memory Service for conversation persistence
- Logging Service for real-time updates
- Graph Workflow for agent reasoning
"""

from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

from src.tools.base import BaseTool
from src.services.logging_service import LoggingService
from src.services.llm_service import LLMService
from src.core.memory import MemoryService
from src.core.graph import create_workflow


class AgentManager:
    """
    Manages agent lifecycle and execution with dependency injection.
    
    Provides clean separation between agent configuration and execution,
    making it easier to test, maintain, and extend.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        memory_service: MemoryService,
        logging_service: LoggingService,
        tools: List[BaseTool]
    ):
        """
        Initialize agent manager with dependencies.
        
        Args:
            llm_service: Service for LLM interactions
            memory_service: Service for conversation memory
            logging_service: Service for real-time logging
            tools: List of tools available to the agent
            
        Usage:
            from src.core.agent import AgentManager
            from src.services.llm_service import LLMService
            from src.services.logging_service import LoggingService
            from src.core.memory import get_memory_service
            from src.core.config import settings
            
            llm_service = LLMService(settings)
            memory_service = get_memory_service()
            logger = LoggingService(settings.logging_url)
            
            manager = AgentManager(
                llm_service=llm_service,
                memory_service=memory_service,
                logging_service=logger,
                tools=[search_tool, scraper_tool]
            )
            
            result = manager.execute_task(
                session_id="user-123",
                message_id="msg-456",
                prompt="Find information about AI"
            )
        """
        self.llm_service = llm_service
        self.memory_service = memory_service
        self.logger = logging_service
        self.tools = tools
        
        # Convert BaseTool instances to LangChain tools
        self.langchain_tools = [tool.as_langchain_tool() for tool in tools]
        
        # Cache for compiled workflows per session (optional optimization)
        self._workflow_cache: Dict[str, Any] = {}
    
    def execute_task(
        self,
        prompt: str,
        message_id: str,
        session_id: str = "default"
    ) -> str:
        """
        Execute a task with the agent.
        
        Args:
            prompt: User's input/question
            message_id: Unique message identifier for tracking
            session_id: Session identifier for conversation memory
            
        Returns:
            str: Agent's final response
            
        Example:
            result = manager.execute_task(
                prompt="What's the weather like?",
                message_id="msg_123",
                session_id="user_456"
            )
        """
        print(f"[AgentManager] Starting task - Session: {session_id}, Message: {message_id}")
        
        try:
            # Log initialization
            self.logger.status("Initializing AI agent...", message_id)
            
            # Get model with tools bound
            model_with_tools = self.llm_service.get_model_with_tools(
                self.langchain_tools
            )
            
            # Create workflow with memory
            checkpointer = self.memory_service.get_checkpointer()
            
            # Logger callback for workflow
            def log_callback(message: str, log_type: str):
                if log_type == "thinking":
                    self.logger.thinking(message, message_id)
                elif log_type == "status":
                    self.logger.status(message, message_id)
            
            workflow_app = create_workflow(
                tools=self.langchain_tools,
                model_with_tools=model_with_tools,
                checkpointer=checkpointer,
                logger_callback=log_callback
            )
            
            self.logger.status("Agent initialized successfully", message_id)
            self.logger.thinking("Starting task execution...", message_id)
            
            # Get session configuration
            session_config = self.memory_service.get_session_config(session_id)
            
            # Execute workflow
            final_answer = self._stream_workflow(
                workflow_app,
                prompt,
                session_config,
                message_id
            )
            
            if final_answer:
                self.logger.status("Task completed successfully", message_id)
                self.logger.response(final_answer, message_id)
                return final_answer
            else:
                error_msg = "Agent finished but no final answer found."
                self.logger.status(error_msg, message_id)
                return "No response generated"
                
        except Exception as e:
            error_msg = f"An error occurred during agent execution: {e}"
            self.logger.error(error_msg, message_id)
            print(f"[AgentManager] Error: {e}")
            return f"Error: {e}"
    
    def _stream_workflow(
        self,
        workflow_app: Any,
        prompt: str,
        session_config: Dict[str, Any],
        message_id: str
    ) -> Optional[str]:
        """
        Stream workflow execution and extract final answer.
        
        Args:
            workflow_app: Compiled LangGraph workflow
            prompt: User prompt
            session_config: Session configuration
            message_id: Message identifier
            
        Returns:
            Final answer from agent or None
        """
        final_answer = None
        response_sent = False
        
        try:
            # Stream the workflow execution
            for step in workflow_app.stream(
                {"messages": [HumanMessage(content=prompt)]},
                config=session_config
            ):
                # Print step for debugging
                print(step)
                
                # Skip if response already sent
                if response_sent:
                    continue
                
                # Check agent node for final response
                if "agent" in step:
                    messages = step['agent']['messages']
                    if messages:
                        last_message = messages[-1]
                        if isinstance(last_message, AIMessage):
                            # Check if this is final answer (no tool calls)
                            tool_calls = getattr(last_message, 'tool_calls', None)
                            if not tool_calls or len(tool_calls) == 0:
                                if hasattr(last_message, 'content') and last_message.content:
                                    final_answer = str(last_message.content)
                                    response_sent = True
                                    break  # Exit immediately
                
                # Log tool executions if needed
                if "tools" in step:
                    print(f"[Tools] {step}")
                    
        except Exception as e:
            print(f"[AgentManager] Streaming error: {e}")
            raise
        
        return final_answer
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages in the session
            
        Note:
            This is a placeholder. Full implementation would query
            the checkpointer for historical messages.
        """
        # TODO: Implement history retrieval from checkpointer
        return []
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if successful
        """
        return self.memory_service.clear_session(session_id)
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return [tool.name for tool in self.tools]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent manager statistics.
        
        Returns:
            dict: Statistics about the manager
        """
        return {
            "tools_count": len(self.tools),
            "tools": self.get_available_tools(),
            "memory": self.memory_service.get_stats(),
            "llm_model": self.llm_service.settings.llm_model,
        }


class SimpleAgentManager:
    """
    Simplified agent manager without session management.
    
    Useful for stateless interactions or testing.
    """
    
    def __init__(self, llm_service: LLMService, tools: List[BaseTool]):
        """
        Initialize simple agent manager.
        
        Args:
            llm_service: Service for LLM interactions
            tools: List of tools available to the agent
        """
        self.llm_service = llm_service
        self.tools = tools
        self.langchain_tools = [tool.as_langchain_tool() for tool in tools]
    
    def execute(self, prompt: str) -> str:
        """
        Execute a single query without session management.
        
        Args:
            prompt: User query
            
        Returns:
            str: Agent response
        """
        from src.core.graph import create_simple_workflow
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Get model with tools
        model = self.llm_service.get_model_with_tools(self.langchain_tools)
        
        # Create stateless workflow
        workflow = create_simple_workflow(self.langchain_tools, model)
        
        # Execute
        result = workflow.invoke({"messages": [HumanMessage(content=prompt)]})
        
        # Extract answer
        messages = result.get('messages', [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and hasattr(last_message, 'content'):
                return str(last_message.content)
        
        return "No response generated"
