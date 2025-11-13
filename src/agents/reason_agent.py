"""
Reason Agent - Planning and Coordination

The "brain" of the multi-agent system that analyzes tasks,
creates execution plans, and coordinates other agents.

Refactored to use component architecture:
- TaskAnalyzer: Task analysis and tool selection
- ExecutionEngine: Task execution and delegation
- ResultProcessor: Result synthesis and goal checking
"""

from typing import List, Dict, Any, Optional
from src.agents.base_agent import (
    BaseAgent, AgentTask, AgentResult, AgentMessage,
    MessageType, TaskPriority, AgentStatus
)
from src.agents.task_analyzer import TaskAnalyzer
from src.agents.execution_engine import ExecutionEngine
from src.agents.result_processor import ResultProcessor
import time


class ReasonAgent(BaseAgent):
    """
    Agent that analyzes tasks and creates execution plans.

    The Reason Agent is responsible for:
    - Breaking down complex tasks into subtasks
    - Identifying which tools/agents are needed
    - Coordinating execution across multiple agents
    - Synthesizing results from multiple sources
    - Maintaining conversation context

    Example:
        reason_agent = ReasonAgent(
            agent_id="reason_1",
            llm_service=llm_service,
            available_tools=["search", "scrape", "calculate"],
            executor_agents=[executor1, executor2]
        )

        task = AgentTask(
            task_type="complex_query",
            description="Find weather in Paris and book restaurant",
            parameters={"query": "..."}
        )

        result = reason_agent.execute(task)
    """

    def __init__(
        self,
        agent_id: str,
        llm_service: Any,
        available_tools: List[str],
        executor_agents: Optional[List[Any]] = None,
        logger: Optional[Any] = None
    ):
        """
        Initialize Reason Agent.

        Args:
            agent_id: Unique identifier for this agent
            llm_service: LLM service for reasoning
            available_tools: List of available tool names
            executor_agents: List of ExecutorAgent instances to delegate to
            logger: Optional logging service
        """
        super().__init__(
            agent_id=agent_id,
            agent_type="reason",
            capabilities=["planning", "coordination", "synthesis", "reasoning"],
            llm_service=llm_service,
            logger=logger
        )

        # Initialize component architecture
        self.task_analyzer = TaskAnalyzer(llm_service)
        self.execution_engine = ExecutionEngine(executor_agents, llm_service)
        self.result_processor = ResultProcessor(llm_service)

        # Legacy attributes for backward compatibility
        self.available_tools = available_tools
        self.executor_agents = executor_agents or []
        self.execution_history: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}

        # Conversation context for multi-turn awareness
        self.conversation_history: List[Dict[str, Any]] = []
        self.original_request: Optional[str] = None
        self.previous_results: List[Dict[str, Any]] = []

    def execute(self, task: AgentTask, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Execute a task by planning and coordinating.

        Args:
            task: Task to execute
            context: Optional execution context

        Returns:
            AgentResult with synthesized results
        """
        start_time = time.time()
        self.state.update_status(AgentStatus.THINKING)
        self.log(f"Reason agent analyzing task: {task.description}")

        try:
            # Step 1: Analyze the task using TaskAnalyzer component
            self.log("Step 1: Analyzing task requirements...")
            analysis = self.task_analyzer.analyze_task(task.description)

            # Step 2: Create execution plan using TaskDecomposer
            self.log("Step 2: Creating execution plan...")
            plan = self._create_plan(task, analysis)

            # Step 3: Execute plan using ExecutionEngine
            if plan.get("needs_delegation", False):
                self.log("Step 3: Task requires delegation to executors")
                subtask_results = self.execution_engine.execute_plan(plan, task)

                # Step 4: Synthesize results using ResultProcessor
                self.log("Step 4: Synthesizing results...")
                final_result = self.result_processor.synthesize_results(task.description, subtask_results)
            else:
                self.log("Step 3: Task can be handled directly")
                final_result = self._handle_simple_task(task, analysis)

            execution_time = time.time() - start_time
            self.state.update_status(AgentStatus.COMPLETED)

            return AgentResult.success_result(
                data=final_result,
                agent_id=self.agent_id,
                execution_time=execution_time,
                metadata={"plan": plan, "analysis": analysis.to_dict()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self.state.update_status(AgentStatus.ERROR, str(e))
            self.log(f"Error in reason agent: {e}", level="error")

            return AgentResult.error_result(
                error=str(e),
                agent_id=self.agent_id,
                execution_time=execution_time
            )

    def can_handle(self, task: AgentTask) -> bool:
        """
        Reason agent can handle any task (it's the coordinator).

        Args:
            task: Task to check

        Returns:
            Always True
        """
        return True

    def _handle_simple_task(self, task: AgentTask, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle simple task directly without delegation.
        For follow-up questions, uses previous context.

        Args:
            task: Task to handle
            analysis: Task analysis

        Returns:
            Direct result
        """
        # Check if this is a follow-up question
        if self._is_followup_question(task.description):
            self.log("Handling follow-up question with previous context")

            # Get the most recent previous result
            if self.previous_results:
                last_result = self.previous_results[-1]
                previous_answer = last_result.get("result", {}).get("answer", "")

                # Build a response with more details from previous context
                answer = f"Based on our previous conversation:\n\n{previous_answer}\n\n"
                answer += "Please let me know if you need any specific aspect explained in more detail."

                return {
                    "task_id": task.task_id,
                    "description": task.description,
                    "answer": answer,
                    "method": "context_based"
                }

        # Default handling for non-follow-up questions
        return {
            "task_id": task.task_id,
            "description": task.description,
            "answer": f"I need more information to help with: {task.description}",
            "method": "direct"
        }

    def _is_followup_question(self, query: str) -> bool:
        """
        Use LLM to detect if query is a follow-up to previous conversation.

        Args:
            query: User's query

        Returns:
            True if follow-up question
        """
        last_query = ""

        # Try to get last query from previous_results first
        if self.previous_results:
            last_result = self.previous_results[-1]
            last_query = last_result.get("task", "")
            self.log(f"Got last_query from previous_results: '{last_query}'")

        # Fallback: use conversation_history if previous_results is empty/broken
        if not last_query and len(self.conversation_history) >= 2:
            self.log("previous_results empty, trying conversation_history")
            # Get last user message (skip current one which hasn't been added yet)
            for msg in reversed(self.conversation_history):
                if msg["role"] == "user":
                    last_query = msg["content"]
                    self.log(f"Got last_query from conversation_history: '{last_query}'")
                    break

        # If still no last_query, can't be follow-up
        if not last_query:
            self.log("No previous query found - cannot be follow-up")
            return False

        # Don't waste LLM call if queries are identical
        if query.lower().strip() == last_query.lower().strip():
            self.log("Queries are identical - not a follow-up")
            return False

        prompt = f"""Is this a follow-up question that refers to previous data?

Previous Query: "{last_query}"
Current Query: "{query}"

A follow-up question:
- Asks to format/transform previous data (table, list, chart, graph)
- Asks to add/modify/filter fields from previous data
- Refers to "it", "that", "the data", "those results", "them"
- Asks for clarification about previous results
- Requests different presentation of same data

NOT a follow-up:
- Completely new topic
- Different data request unrelated to previous
- New search query

Answer ONLY: yes or no

Answer:"""

        try:
            if not self.llm_service:
                self.log("No LLM service, cannot detect follow-up")
                return False

            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            answer = response.content.strip().lower()

            is_followup = "yes" in answer
            self.log(f"Follow-up detection: {is_followup} ('{query}' vs '{last_query}')")
            return is_followup

        except Exception as e:
            self.log(f"Follow-up detection failed: {e}")
            # Fallback: check for very obvious patterns
            query_lower = query.lower().strip()
            return any(word in query_lower for word in ["table", "format", "show", "display"]) and len(query.split()) < 10

    def _create_plan(self, task: AgentTask, analysis) -> Dict[str, Any]:
        """
        Create execution plan using TaskDecomposer.

        Args:
            task: Task to plan for
            analysis: TaskAnalysis object

        Returns:
            Execution plan
        """
        # Use task decomposer to create the plan
        if self.task_analyzer.task_decomposer:
            context = {
                "query_params": analysis.query_params,
                "task_type": analysis.detected_type,
                "task_structure": analysis.task_structure,
                "required_fields": analysis.required_fields
            }

            subtasks = self.task_analyzer.task_decomposer.decompose(
                task.description,
                task.task_id,
                context
            )

            plan = {
                "needs_delegation": len(subtasks) > 0,
                "complexity": analysis.complexity,
                "subtasks": subtasks,
                "required_fields": analysis.required_fields,
                "original_task_id": task.task_id,
                "task_structure": analysis.task_structure
            }

            return plan
        else:
            # Fallback if no decomposer
            return {
                "needs_delegation": False,
                "complexity": "simple",
                "subtasks": [],
                "required_fields": [],
                "original_task_id": task.task_id,
                "task_structure": {"type": "single"}
            }

    def create_plan(self, task: AgentTask) -> Dict[str, Any]:
        """
        Public method to create plan without execution.

        Args:
            task: Task to plan for

        Returns:
            Execution plan
        """
        analysis = self.task_analyzer.analyze_task(task.description)
        return self._create_plan(task, analysis)

    def delegate_task(self, subtask: Dict[str, Any], executor_id: str) -> AgentMessage:
        """
        Create delegation message for executor.

        Args:
            subtask: Subtask to delegate
            executor_id: ID of executor agent

        Returns:
            AgentMessage for delegation
        """
        return AgentMessage(
            from_agent=self.agent_id,
            to_agent=executor_id,
            message_type=MessageType.REQUEST,
            payload=subtask,
            metadata={"delegation": True}
        )

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Get execution history.

        Returns:
            List of past executions
        """
        return self.execution_history

    def clear_context(self) -> None:
        """Clear execution context."""
        self.context.clear()
        self.execution_history.clear()
