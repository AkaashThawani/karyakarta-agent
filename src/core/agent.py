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

# Multi-agent imports
from src.agents import ReasonAgent, ExecutorAgent, AgentTask, TaskPriority
from src.routing import ToolRegistry, ToolRouter, RoutingStrategy, ToolCategory, CostLevel


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


class MultiAgentManager(AgentManager):
    """
    Extended Agent Manager with multi-agent system support.
    
    Adds intelligent tool routing, reason/executor agent coordination,
    and advanced task management on top of the base AgentManager.
    
    Example:
        manager = MultiAgentManager(
            llm_service=llm_service,
            memory_service=memory_service,
            logging_service=logger,
            tools=[search_tool, scraper_tool],
            enable_routing=True,
            routing_strategy=RoutingStrategy.BALANCED
        )
        
        # Use multi-agent execution
        result = manager.execute_task_multi_agent(
            prompt="Find and analyze Python tutorials",
            message_id="msg_123",
            session_id="user_456"
        )
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        memory_service: MemoryService,
        logging_service: LoggingService,
        tools: List[BaseTool],
        enable_routing: bool = True,
        routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ):
        """
        Initialize multi-agent manager.
        
        Args:
            llm_service: Service for LLM interactions
            memory_service: Service for conversation memory
            logging_service: Service for real-time logging
            tools: List of tools available
            enable_routing: Whether to enable intelligent tool routing
            routing_strategy: Default routing strategy
        """
        # Initialize base class
        super().__init__(llm_service, memory_service, logging_service, tools)
        
        # Initialize tool registry and router
        self.registry = ToolRegistry()
        self.enable_routing = enable_routing
        
        # Register all tools
        self._register_tools()
        
        # Create router
        self.router = ToolRouter(self.registry, strategy=routing_strategy)
        
        # Create executor agent
        self.executor = ExecutorAgent(
            agent_id="executor_main",
            tools=tools,
            logger=logging_service
        )
        
        # Create reason agent with executor agent reference
        self.reason_agent = ReasonAgent(
            agent_id="reason_main",
            llm_service=llm_service,
            available_tools=[t.name for t in tools],
            executor_agents=[self.executor],  # Pass executor to reason agent
            logger=logging_service
        )
        
        print("[MultiAgentManager] Multi-agent system initialized")
        print(f"[MultiAgentManager] Routing: {enable_routing}, Strategy: {routing_strategy.value}")
    
    def _register_tools(self) -> None:
        """Register all tools in the registry with metadata."""
        tool_categories = {
            "google_search": ToolCategory.SEARCH,
            "browse_website": ToolCategory.SCRAPING,
            "scraper": ToolCategory.SCRAPING,
            "calculator": ToolCategory.CALCULATION,
            "extract_data": ToolCategory.DATA_PROCESSING,
        }
        
        for tool in self.tools:
            # Determine category
            category = ToolCategory.OTHER
            for key, cat in tool_categories.items():
                if key in tool.name.lower():
                    category = cat
                    break
            
            # Register with default metadata
            self.registry.register(
                name=tool.name,
                description=tool.description,
                capabilities={tool.name, category.value},
                category=category,
                cost=CostLevel.FREE,
                avg_latency=1.0,
                reliability=95.0
            )
    
    def execute_task_multi_agent(
        self,
        prompt: str,
        message_id: str,
        session_id: str = "default",
        use_reason_agent: bool = True
    ) -> str:
        """
        Execute task using multi-agent system.
        
        Args:
            prompt: User's input/question
            message_id: Unique message identifier
            session_id: Session identifier
            use_reason_agent: Whether to use reason agent for planning
            
        Returns:
            str: Final response
        """
        print(f"[MultiAgentManager] Multi-agent execution - Session: {session_id}")
        
        try:
            self.logger.thinking("Analyzing your request with multi-agent system...", message_id)
            
            # Create task
            task = AgentTask(
                task_type="user_query",
                description=prompt,
                parameters={"query": prompt, "session_id": session_id},
                priority=TaskPriority.MEDIUM
            )
            
            if use_reason_agent:
                # Use reason agent for complex tasks
                self.logger.status("Planning execution strategy...", message_id)
                result = self.reason_agent.execute(task)
            else:
                # Direct execution with executor
                self.logger.status("Executing task directly...", message_id)
                
                # Route to best tool if routing enabled
                if self.enable_routing:
                    tool_metadata = self.router.route(task)
                    if tool_metadata:
                        self.logger.status(f"Using tool: {tool_metadata.name}", message_id)
                        # Update task type to match routed tool
                        task.task_type = tool_metadata.name
                
                result = self.executor.execute(task)
            
            # Update registry stats
            if self.enable_routing and result.metadata.get("tool"):
                tool_name = result.metadata["tool"]
                self.registry.update_stats(
                    tool_name,
                    result.is_success(),
                    result.execution_time
                )
            
            if result.is_success():
                final_answer = self._format_result(result.data)
                self.logger.status("Task completed successfully", message_id)
                self.logger.response(final_answer, message_id)
                
                # Save to session
                self._save_to_session(session_id, message_id, prompt, final_answer)
                
                return final_answer
            else:
                error_msg = result.get_error() or "Task execution failed"
                self.logger.error(error_msg, message_id)
                return f"Error: {error_msg}"
                
        except Exception as e:
            error_msg = f"Multi-agent execution error: {e}"
            self.logger.error(error_msg, message_id)
            print(f"[MultiAgentManager] Error: {e}")
            return f"Error: {e}"
    
    def _format_result(self, data: Any) -> str:
        """Format result data into readable string."""
        if isinstance(data, dict):
            if "answer" in data:
                return str(data["answer"])
            elif "result" in data:
                return str(data["result"])
            # Format dict nicely
            return "\n".join(f"{k}: {v}" for k, v in data.items() if v)
        return str(data)
    
    def _save_to_session(
        self,
        session_id: str,
        message_id: str,
        prompt: str,
        response: str
    ) -> None:
        """Save messages to session."""
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
                content=response,
                tokens=len(response.split())
            )
            
            print(f"[MultiAgentManager] Messages saved to session {session_id}")
        except Exception as e:
            print(f"[MultiAgentManager] Failed to save messages: {e}")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Dictionary of routing stats
        """
        return {
            "router_stats": self.router.get_stats_summary(),
            "registry_summary": self.registry.get_summary(),
            "executor_stats": self.executor.get_execution_stats(),
            "reason_history": len(self.reason_agent.get_execution_history())
        }
    
    def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        """
        Change routing strategy.
        
        Args:
            strategy: New routing strategy
        """
        self.router.set_strategy(strategy)
        print(f"[MultiAgentManager] Routing strategy changed to: {strategy.value}")
    
    def add_tool_dynamically(
        self,
        tool: BaseTool,
        category: ToolCategory = ToolCategory.OTHER,
        cost: CostLevel = CostLevel.FREE
    ) -> None:
        """
        Add a new tool at runtime.
        
        Args:
            tool: Tool to add
            category: Tool category
            cost: Cost level
        """
        # Add to base tools
        self.tools.append(tool)
        self.langchain_tools.append(tool.as_langchain_tool())
        
        # Register in registry
        self.registry.register(
            name=tool.name,
            description=tool.description,
            capabilities={tool.name, category.value},
            category=category,
            cost=cost,
            avg_latency=1.0,
            reliability=95.0
        )
        
        # Add to executor
        self.executor.add_tool(tool)
        
        print(f"[MultiAgentManager] Tool added: {tool.name}")
    
    def get_multi_agent_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive multi-agent statistics.
        
        Returns:
            Complete statistics dictionary
        """
        base_stats = self.get_stats()
        routing_stats = self.get_routing_stats()
        
        return {
            **base_stats,
            "multi_agent": routing_stats,
            "mode": "multi_agent"
        }
