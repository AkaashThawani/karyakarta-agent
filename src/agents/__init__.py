"""
Multi-Agent System

Provides base classes and utilities for building multi-agent systems.

Classes:
    - MessageType: Enum for message types
    - AgentMessage: Communication between agents
    - AgentStatus: Enum for agent states
    - AgentState: Agent state tracking
    - AgentResult: Standardized execution results
    - TaskPriority: Enum for task priorities
    - AgentTask: Task representation
    - BaseAgent: Abstract base class for all agents

Usage:
    from src.agents import BaseAgent, AgentTask, AgentResult
    
    class MyAgent(BaseAgent):
        def execute(self, task, context):
            # Implementation
            return AgentResult.success_result(
                data=result,
                agent_id=self.agent_id
            )
        
        def can_handle(self, task):
            return task.task_type in self.state.capabilities
"""

from src.agents.base_agent import (
    # Enums
    MessageType,
    AgentStatus,
    TaskPriority,
    
    # Core Classes
    AgentMessage,
    AgentState,
    AgentResult,
    AgentTask,
    BaseAgent,
)

# Import specialized agents
from src.agents.reason_agent import ReasonAgent
from src.agents.executor_agent import ExecutorAgent

__all__ = [
    # Enums
    "MessageType",
    "AgentStatus",
    "TaskPriority",
    
    # Core Classes
    "AgentMessage",
    "AgentState",
    "AgentResult",
    "AgentTask",
    "BaseAgent",
    
    # Specialized Agents
    "ReasonAgent",
    "ExecutorAgent",
]
