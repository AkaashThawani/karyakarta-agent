"""
Base Agent Architecture

Define Core classes for multi agent systems:
- AgentMessage: Communication between agents
- AgentState: Agent state tracking
- AgentResult: Standardized results
- AgentTask: Task Representation
- BaseAgent: Abstract base class for all agents
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from uuid import uuid4


class MessageType(Enum):
    """
    Types of messages that agents can send to each other.
    
    - REQUEST: Agent can ask another agent to perform task
    - RESPONSE: Reply to REQUEST with result
    - STATUS: Progress update on ongoing task
    - ERROR: Something went wrong
    - BROADCAST: Message to all other agents
    """
    REQUEST = "request"
    RESPONSE = "response"
    STATUS = "status"
    ERROR = "error"
    BROADCAST = "broadcast"


class AgentMessage(BaseModel):
    """
    Message format for agent communication.
    
    Example:
        # Create a message
        message = AgentMessage(
            from_agent="reason_agent",
            to_agent="executor_agent",
            message_type=MessageType.REQUEST,
            payload={"task": "search", "query": "Python"}
        )
        
        # Convert to dict
        msg_dict = message.to_dict()
        
        # Create from dict
        new_message = AgentMessage.from_dict(msg_dict)
        
        # Validate
        if message.is_valid():
            print("Message is valid")
    """
    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:8]}")
    from_agent: str = Field(..., description="ID of agent sending message")
    to_agent: str = Field(..., description="ID of agent receiving")
    message_type: MessageType = Field(..., description="Type of message")
    payload: Dict[str, Any] = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary format.
        
        Returns:
            Dict with all message fields
        """
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """
        Create AgentMessage from dictionary.
        
        Args:
            data: Dictionary with message fields
            
        Returns:
            AgentMessage instance
        """
        # Convert string back to enum
        if isinstance(data.get("message_type"), str):
            data["message_type"] = MessageType(data["message_type"])
        
        # Convert string back to datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        
        return cls(**data)
    
    def is_valid(self) -> bool:
        """
        Validate message has all required fields.
        
        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        if not self.id or not self.from_agent or not self.to_agent:
            return False
        
        # Check message_type is valid
        if not isinstance(self.message_type, MessageType):
            return False
        
        # Check payload exists for REQUEST and RESPONSE
        if self.message_type in [MessageType.REQUEST, MessageType.RESPONSE]:
            if not self.payload:
                return False
        
        return True
    
    def is_request(self) -> bool:
        """Check if this is a request message."""
        return self.message_type == MessageType.REQUEST
    
    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.message_type == MessageType.RESPONSE
    
    def is_error(self) -> bool:
        """Check if this is an error message."""
        return self.message_type == MessageType.ERROR
    
    def create_response(self, payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> 'AgentMessage':
        """
        Create a response message to this message.
        
        Args:
            payload: Response data
            metadata: Optional metadata
            
        Returns:
            New AgentMessage as response
        """
        return AgentMessage(
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            message_type=MessageType.RESPONSE,
            payload=payload,
            metadata=metadata or {}
        )


class AgentStatus(Enum):
    """
    Possible states an agent can be in.
    
    - IDLE: Agent is ready for new task
    - THINKING: Agent is analyzing/planning
    - EXECUTING: Agent is performing a task
    - WAITING: Agent is waiting for response/resource
    - ERROR: Agent encountered error
    - COMPLETED: Agent finished its work
    """
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentState(BaseModel):
    """
    Tracks the current state and history of an agent.
    
    Example:
        state = AgentState(
            status=AgentStatus.IDLE,
            capabilities=["search", "scrape"]
        )
        
        # Start a task
        state.start_task({"task_id": "t1", "type": "search"})
        
        # Complete it
        state.complete_task(success=True)
    """
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    current_task: Optional[Dict[str, Any]] = Field(default=None)
    task_history: List[Dict[str, Any]] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=lambda: {
        "task_completed": 0,
        "task_failed": 0,
        "total_execution_time": 0.0
    })
    error_message: Optional[str] = Field(default=None)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def update_status(self, new_status: AgentStatus, error_msg: Optional[str] = None) -> None:
        """
        Update agent status.
        
        Args:
            new_status: New status to set
            error_msg: Optional error message if status is ERROR
        """
        self.status = new_status
        if error_msg:
            self.error_message = error_msg
        self.last_updated = datetime.now()
    
    def start_task(self, task: Dict[str, Any]) -> None:
        """
        Start a new task.
        
        Args:
            task: Task details
        """
        self.current_task = task
        self.status = AgentStatus.EXECUTING
        self.last_updated = datetime.now()
    
    def complete_task(self, success: bool, result: Any = None) -> None:
        """
        Complete the current task.
        
        Args:
            success: Whether task completed successfully
            result: Optional task result
        """
        if self.current_task:
            self.task_history.append({
                "task": self.current_task,
                "completed_at": datetime.now().isoformat(),
                "success": success,
                "result": result
            })
            
            # Update correct metric based on success
            if success:
                self.metrics["task_completed"] += 1
            else:
                self.metrics["task_failed"] += 1
            
            self.current_task = None
            self.status = AgentStatus.IDLE
            self.last_updated = datetime.now()
    
    def add_capability(self, capability: str) -> None:
        """
        Add a capability to this agent.
        
        Args:
            capability: Capability name to add
        """
        if capability not in self.capabilities:
            self.capabilities.append(capability)
    
    def can_handle(self, task_type: str) -> bool:
        """
        Check if agent can handle a task type.
        
        Args:
            task_type: Type of task
            
        Returns:
            True if agent has capability for this task
        """
        return task_type in self.capabilities
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.
        
        Returns:
            Dictionary of metrics
        """
        success_rate = 0.0
        total_tasks = self.metrics["task_completed"] + self.metrics["task_failed"]
        if total_tasks > 0:
            success_rate = (self.metrics["task_completed"] / total_tasks) * 100
        
        return {
            **self.metrics,
            "success_rate": round(success_rate, 2),
            "total_tasks": total_tasks
        }
    
    def reset(self) -> None:
        """Reset agent to initial state."""
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.task_history = []
        self.capabilities = []
        self.metrics = {
            "task_completed": 0,
            "task_failed": 0,
            "total_execution_time": 0.0
        }
        self.error_message = None
        self.last_updated = datetime.now()


class AgentResult(BaseModel):
    """
    Standardized result from agent execution.
    
    Example:
        result = AgentResult(
            success=True,
            data={"findings": "..."},
            agent_id="executor_1",
            execution_time=2.5
        )
        
        if result.is_success():
            print(result.data)
        else:
            print(result.get_error())
    """
    success: bool = Field(..., description="Whether execution succeeded")
    data: Any = Field(default=None, description="Result data")
    agent_id: str = Field(..., description="ID of agent that produced result")
    execution_time: float = Field(default=0.0, description="Execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.now)
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Validation results (valid, reason, needs_replan)")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert result to dictionary format.
        
        Returns:
            Dict with all result fields
        """
        return {
            "success": self.success,
            "data": self.data,
            "agent_id": self.agent_id,
            "execution_time": self.execution_time,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentResult':
        """
        Create AgentResult from dictionary.
        
        Args:
            data: Dictionary with result fields
            
        Returns:
            AgentResult instance
        """
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
    
    def is_success(self) -> bool:
        """
        Check if execution was successful.
        
        Returns:
            True if successful, False otherwise
        """
        return self.success
    
    def get_error(self) -> Optional[str]:
        """
        Get error message if execution failed.
        
        Returns:
            Error message or None if successful
        """
        return self.error if not self.success else None
    
    @classmethod
    def success_result(cls, data: Any, agent_id: str, execution_time: float = 0.0, 
                      metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """
        Create a successful result.
        
        Args:
            data: Result data
            agent_id: ID of agent
            execution_time: Execution time in seconds
            metadata: Optional metadata
            
        Returns:
            AgentResult with success=True
        """
        return cls(
            success=True,
            data=data,
            agent_id=agent_id,
            execution_time=execution_time,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(cls, error: str, agent_id: str, execution_time: float = 0.0,
                    metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """
        Create an error result.
        
        Args:
            error: Error message
            agent_id: ID of agent
            execution_time: Execution time in seconds
            metadata: Optional metadata
            
        Returns:
            AgentResult with success=False
        """
        return cls(
            success=False,
            error=error,
            agent_id=agent_id,
            execution_time=execution_time,
            metadata=metadata or {}
        )


class TaskPriority(Enum):
    """
    Priority levels for tasks.
    
    - LOW: Can be done when resources available
    - MEDIUM: Normal priority
    - HIGH: Important, should be done soon
    - URGENT: Critical, do immediately
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AgentTask(BaseModel):
    """
    Standardized task format for agents.
    
    Example:
        task = AgentTask(
            task_type="search",
            description="Find Python tutorials",
            parameters={"query": "Python tutorials"},
            priority=TaskPriority.MEDIUM
        )
        
        # Assign to agent
        task.assign_to("executor_1")
        
        # Check if ready
        if task.is_ready():
            # Execute task
            pass
    """
    task_id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:8]}")
    task_type: str = Field(..., description="Type of task (search, scrape, etc.)")
    description: str = Field(..., description="Human-readable task description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    dependencies: List[str] = Field(default_factory=list, description="Task IDs that must complete first")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")
    created_at: datetime = Field(default_factory=datetime.now)
    assigned_to: Optional[str] = Field(default=None, description="Agent ID assigned to")
    status: str = Field(default="pending", description="Task status")
    completed_at: Optional[datetime] = Field(default=None)
    result: Optional[AgentResult] = Field(default=None)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to dictionary format.
        
        Returns:
            Dict with all task fields
        """
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "assigned_to": self.assigned_to,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result.to_dict() if self.result else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentTask':
        """
        Create AgentTask from dictionary.
        
        Args:
            data: Dictionary with task fields
            
        Returns:
            AgentTask instance
        """
        if isinstance(data.get("priority"), str):
            data["priority"] = TaskPriority(data["priority"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("completed_at"), str):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        if isinstance(data.get("result"), dict):
            data["result"] = AgentResult.from_dict(data["result"])
        return cls(**data)
    
    def has_dependencies(self) -> bool:
        """
        Check if task has dependencies.
        
        Returns:
            True if has dependencies, False otherwise
        """
        return len(self.dependencies) > 0
    
    def is_ready(self, completed_tasks: Optional[List[str]] = None) -> bool:
        """
        Check if task is ready to execute.
        
        Args:
            completed_tasks: List of completed task IDs
            
        Returns:
            True if ready (no dependencies or all dependencies complete)
        """
        if not self.has_dependencies():
            return True
        
        if completed_tasks is None:
            return False
        
        # Check if all dependencies are in completed tasks
        return all(dep_id in completed_tasks for dep_id in self.dependencies)
    
    def assign_to(self, agent_id: str) -> None:
        """
        Assign task to an agent.
        
        Args:
            agent_id: ID of agent to assign to
        """
        self.assigned_to = agent_id
        self.status = "assigned"
    
    def mark_in_progress(self) -> None:
        """Mark task as in progress."""
        self.status = "in_progress"
    
    def mark_completed(self, result: AgentResult) -> None:
        """
        Mark task as completed.
        
        Args:
            result: Result of task execution
        """
        self.status = "completed" if result.success else "failed"
        self.completed_at = datetime.now()
        self.result = result
    
    def is_high_priority(self) -> bool:
        """Check if task is high or urgent priority."""
        return self.priority in [TaskPriority.HIGH, TaskPriority.URGENT]


# Import ABC for abstract base class
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    All agents must inherit from this class and implement the abstract methods.
    This ensures consistent interface across all agent types.
    
    Example:
        class MyAgent(BaseAgent):
            def execute(self, task, context):
                # Implementation
                result = self._do_work(task)
                return AgentResult.success_result(
                    data=result,
                    agent_id=self.agent_id
                )
            
            def can_handle(self, task):
                return task.task_type in self.state.capabilities
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        capabilities: List[str],
        llm_service: Optional[Any] = None,
        logger: Optional[Any] = None
    ):
        """
        Initialize base agent.
        
        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type of agent (reason, executor, etc.)
            capabilities: List of capabilities this agent has
            llm_service: Optional LLM service for reasoning
            logger: Optional logging service
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state = AgentState(capabilities=capabilities)
        self.llm_service = llm_service
        self.logger = logger
        self.message_queue: List[AgentMessage] = []
    
    @abstractmethod
    def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Execute a task. Must be implemented by subclasses.
        
        Args:
            task: Task to execute
            context: Optional context information
            
        Returns:
            AgentResult with execution outcome
        """
        pass
    
    @abstractmethod
    def can_handle(self, task: AgentTask) -> bool:
        """
        Check if this agent can handle a task. Must be implemented by subclasses.
        
        Args:
            task: Task to check
            
        Returns:
            True if agent can handle this task
        """
        pass
    
    def send_message(self, message: AgentMessage) -> None:
        """
        Send a message to another agent.
        
        Args:
            message: Message to send
        """
        if self.logger:
            self.logger.status(f"Agent {self.agent_id} sending message to {message.to_agent}", "")
        # In real implementation, this would go through a message bus
        # For now, just log it
    
    def receive_message(self, message: AgentMessage) -> None:
        """
        Receive and queue a message.
        
        Args:
            message: Message received
        """
        if message.is_valid():
            self.message_queue.append(message)
            if self.logger:
                self.logger.status(f"Agent {self.agent_id} received {message.message_type.value} from {message.from_agent}", "")
    
    def process_messages(self) -> List[AgentMessage]:
        """
        Process all queued messages.
        
        Returns:
            List of messages processed
        """
        messages = self.message_queue.copy()
        self.message_queue.clear()
        return messages
    
    def get_status(self) -> AgentState:
        """
        Get current agent state.
        
        Returns:
            Current AgentState
        """
        return self.state
    
    def reset(self) -> None:
        """Reset agent to initial state."""
        self.state.reset()
        self.message_queue.clear()
    
    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message.
        
        Args:
            message: Message to log
            level: Log level (info, warning, error)
        """
        if self.logger:
            if level == "error":
                self.logger.error(message, "")
            else:
                self.logger.status(message, "")
    
    def __repr__(self) -> str:
        """String representation of agent."""
        return f"{self.__class__.__name__}(id={self.agent_id}, type={self.agent_type}, status={self.state.status.value})"
