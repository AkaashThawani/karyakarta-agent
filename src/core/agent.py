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
from src.services.session_service import get_session_service

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
        
        # Prepare workflow components once
        self.model_with_tools = self.llm_service.get_model_with_tools(self.langchain_tools)
        self.checkpointer = self.memory_service.get_checkpointer()
        self.workflow_app = None  # Will be created on first use
        
        print("[AgentManager] Instance initialized with tools")
    
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
        print(f"[AgentManager] Processing task - Session: {session_id}, Message: {message_id}")
        
        try:
            # Create workflow on first use (cached after that)
            if self.workflow_app is None:
                print("[AgentManager] Creating workflow for first time")
                
                # Logger callback for workflow
                def log_callback(message: str, log_type: str):
                    if log_type == "thinking":
                        self.logger.thinking(message, message_id)
                    elif log_type == "status":
                        self.logger.status(message, message_id)
                
                self.workflow_app = create_workflow(
                    tools=self.langchain_tools,
                    model_with_tools=self.model_with_tools,
                    checkpointer=self.checkpointer,
                    logger_callback=log_callback
                )
            
            self.logger.thinking("Processing your request...", message_id)
            
            # Get session configuration
            session_config = self.memory_service.get_session_config(session_id)
            
            # Execute workflow
            final_answer = self._stream_workflow(
                self.workflow_app,
                prompt,
                session_config,
                message_id
            )
            
            if final_answer:
                self.logger.status("Task completed successfully", message_id)
                self.logger.response(final_answer, message_id)
                
                # Save messages to session
                try:
                    session_service = get_session_service()
                    
                    # Save user message
                    session_service.add_message_to_session(
                        session_id=session_id,
                        message_id=f"{message_id}_user",
                        role="user",
                        content=prompt,
                        tokens=len(prompt.split())
                    )
                    
                    # Save agent response
                    session_service.add_message_to_session(
                        session_id=session_id,
                        message_id=message_id,
                        role="agent",
                        content=final_answer,
                        tokens=len(final_answer.split())
                    )
                    
                    print(f"[AgentManager] Messages saved to session {session_id}")
                except Exception as e:
                    print(f"[AgentManager] Failed to save messages: {e}")
                
                return final_answer
            else:
                # Agent returned empty response - send error to unlock UI
                error_msg = "I apologize, but I couldn't generate a response. Please try rephrasing your question or try again."
                self.logger.error(error_msg, message_id)
                print(f"[AgentManager] Empty response detected - sending error to unlock UI")
                return error_msg
                
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
                                    content = last_message.content
                                    
                                    # Handle Gemini's list of content objects
                                    if isinstance(content, list):
                                        print(f"[AgentManager] Parsing list content: {len(content)} items")
                                        text_parts = []
                                        for item in content:
                                            if isinstance(item, dict) and item.get('type') == 'text':
                                                text_parts.append(item.get('text', ''))
                                        final_answer = ' '.join(text_parts).strip()
                                    else:
                                        final_answer = str(content)
                                    
                                    if final_answer:
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
