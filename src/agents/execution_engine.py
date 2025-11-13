"""
Execution Engine Component

Responsible for orchestrating task execution, managing delegation to executors,
handling parallel execution, and validating step success.
"""

from typing import List, Dict, Any, Optional
import asyncio
import json
import time
from datetime import datetime


class ExecutionContext:
    """Context for tracking execution state and accumulated data."""

    def __init__(self):
        self.accumulated_data: Dict[str, Dict[str, Any]] = {}
        self.follow_up_counts: Dict[str, int] = {}
        self.extraction_tasks_added = False

    def add_result(self, step_name: str, tool_name: str, result: Dict[str, Any], extracted_outputs: Dict[str, Any]) -> None:
        """Add a result to the accumulated data."""
        self.accumulated_data[step_name] = {
            "tool": tool_name,
            "result": result,
            "extracted": extracted_outputs,
            "timestamp": datetime.now().isoformat()
        }


class ExecutionEngine:
    """
    Component responsible for executing tasks through delegation to executors.

    Handles:
    - Sequential and adaptive execution
    - Parallel execution of independent subtasks
    - Step validation and replanning
    - Data flow resolution between steps
    """

    def __init__(self, executor_agents: Optional[List[Any]] = None, llm_service: Any = None):
        """
        Initialize ExecutionEngine.

        Args:
            executor_agents: List of executor agents to delegate to
            llm_service: LLM service for replanning
        """
        self.executor_agents = executor_agents or []
        self.llm_service = llm_service
        self.max_follow_ups_per_tool = 5

    def execute_plan(self, plan: Optional[Dict[str, Any]], task: Any) -> List[Dict[str, Any]]:
        """
        Execute a plan created by ReasonAgent.

        Args:
            plan: Execution plan with subtasks (can be None)
            task: Original AgentTask

        Returns:
            List of subtask results
        """
        if not plan:
            print("[EXECUTION_ENGINE] No plan provided, returning empty results")
            return []

        subtasks = plan.get("subtasks", [])
        return self.execute_delegation(subtasks, plan)

    def execute_delegation(self, subtasks: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute tasks by delegating to executor agents with automatic data flow resolution.

        Args:
            subtasks: List of subtasks to delegate
            plan: Optional execution plan with extraction settings

        Returns:
            List of results from executors
        """
        # Check if this is an adaptive task
        task_type = plan.get("task_structure", {}).get("type", "sequential") if plan else "sequential"

        if task_type == "adaptive":
            print(f"[EXECUTION_ENGINE] 🔄 Using ADAPTIVE execution (incremental planning)")
            return self._execute_adaptive(subtasks, plan)
        else:
            print(f"[EXECUTION_ENGINE] 📋 Using SEQUENTIAL execution (with validation)")
            return self._execute_sequential(subtasks, plan)

    def _execute_adaptive(self, initial_steps: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute adaptively - plan incrementally based on observations.

        Args:
            initial_steps: Initial steps (usually just navigation)
            plan: Execution plan with goal

        Returns:
            List of all execution results
        """
        from src.agents.result_processor import ResultProcessor

        resolver = self._get_data_flow_resolver()
        result_processor = ResultProcessor(self.llm_service)
        results = []
        accumulated_data = {}

        if plan:
            goal = plan.get("task_structure", {}).get("goal", plan.get("original_task_desc", ""))
        else:
            goal = ""
        max_iterations = 10  # Prevent infinite loops

        print(f"[EXECUTION_ENGINE] 🎯 Adaptive execution goal: {goal}")
        print(f"[EXECUTION_ENGINE] 🎯 Starting with {len(initial_steps)} initial step(s)")

        current_steps = initial_steps
        iteration = 0

        while iteration < max_iterations and current_steps:
            iteration += 1
            print(f"\n[EXECUTION_ENGINE] === Adaptive Iteration {iteration}/{max_iterations} ===")

            # Execute next step
            step = current_steps[0]
            result = self._execute_single_subtask(step, len(results), accumulated_data, resolver, plan)
            results.append(result)

            # Store in accumulated data
            tool_name = step["tool"]
            extracted_outputs = resolver.extract_outputs(tool_name=tool_name, raw_result=result["data"])

            step_name = f"step_{len(results)-1}_{tool_name}"
            accumulated_data[step_name] = {
                "tool": tool_name,
                "result": result,
                "extracted": extracted_outputs,
                "timestamp": datetime.now().isoformat()
            }

            # Check if goal achieved
            if result_processor.check_goal_achieved(results, goal, plan):
                print(f"[EXECUTION_ENGINE] ✅ Goal achieved after {iteration} iterations!")
                break

            # Plan next steps based on current state
            print(f"[EXECUTION_ENGINE] 🔍 Planning next steps based on current state...")
            next_steps = self._plan_next_steps_adaptive(
                goal=goal,
                current_results=results,
                accumulated_data=accumulated_data
            )

            if not next_steps:
                print(f"[EXECUTION_ENGINE] ⚠️ No more steps to plan, stopping")
                break

            print(f"[EXECUTION_ENGINE] 💡 Planned {len(next_steps)} next step(s)")
            current_steps = next_steps

        if iteration >= max_iterations:
            print(f"[EXECUTION_ENGINE] ⚠️ Max iterations reached ({max_iterations})")

        return results

    def _execute_sequential(self, subtasks: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute sequentially with validation and replanning.

        Args:
            subtasks: List of subtasks
            plan: Execution plan

        Returns:
            List of results
        """
        # Initialize DataFlowResolver for automatic data flow
        resolver = self._get_data_flow_resolver()
        print("[EXECUTION_ENGINE] 🔄 Using DataFlowResolver for automatic parameter resolution")

        results = []
        context = ExecutionContext()

        i = 0
        while i < len(subtasks):
            subtask = subtasks[i]
            tool_name = subtask["tool"]

            print(f"[EXECUTION_ENGINE] === Processing Subtask {i+1}/{len(subtasks)}: {tool_name} ===")

            # Check if this subtask can run in parallel with others
            parallel_group = self._identify_parallel_group(subtasks, i, context.accumulated_data)

            if len(parallel_group) > 1:
                # Execute multiple subtasks in parallel
                print(f"[EXECUTION_ENGINE] 🚀 Launching {len(parallel_group)} subtasks in parallel!")

                parallel_results = self._execute_parallel_subtasks(
                    parallel_group,
                    context.accumulated_data,
                    resolver,
                    plan
                )

                # Add all parallel results to our results list
                results.extend(parallel_results)

                # Update accumulated data with all parallel results
                for j, result in enumerate(parallel_results):
                    subtask_idx = parallel_group[j]["index"]
                    tool_name = parallel_group[j]["subtask"]["tool"]

                    # Automatic output extraction
                    extracted_outputs = resolver.extract_outputs(
                        tool_name=tool_name,
                        raw_result=result["data"]
                    )

                    # Store in accumulated data
                    step_name = f"step_{subtask_idx}_{tool_name}"
                    context.add_result(step_name, tool_name, result, extracted_outputs)

                # Skip ahead past all the parallel subtasks we just executed
                i += len(parallel_group)
                print(f"[EXECUTION_ENGINE] ✅ Parallel execution complete, advancing to subtask {i+1}")

            else:
                # Execute single subtask
                result = self._execute_single_subtask(
                    subtask, i, context.accumulated_data, resolver, plan
                )

                # Validate step success and trigger replanning if needed
                validation = self._validate_step_success(
                    subtask, result, context.accumulated_data, plan
                )

                if not validation['valid'] and validation['needs_replan']:
                    print(f"[EXECUTION_ENGINE] 🔄 Step {i+1} failed validation: {validation['reason']}")
                    print(f"[EXECUTION_ENGINE] 🔄 Triggering dynamic replanning...")

                    # Trigger replanning with context
                    original_desc = plan.get('original_task_desc', subtask['description']) if plan else subtask['description']
                    new_subtasks = self._dynamic_replan(
                        original_task_desc=original_desc,
                        failed_step=subtask,
                        validation_result=validation,
                        context={
                            'previous_attempt': subtask,
                            'result': result,
                            'accumulated_data': context.accumulated_data
                        }
                    )

                    if new_subtasks:
                        # Replace remaining subtasks with new plan
                        print(f"[EXECUTION_ENGINE] ✅ Generated {len(new_subtasks)} new steps via replanning")
                        subtasks = subtasks[:i+1] + new_subtasks
                        # Don't append this failed result, continue with new plan
                        i += 1
                        continue
                    else:
                        print(f"[EXECUTION_ENGINE] ⚠️ Replanning failed, continuing with original plan")

                # Check for incomplete data and create follow-up tasks
                if result.get("success") and result.get("metadata", {}).get("complete") == False:
                    suggested_action = result["metadata"].get("suggested_action")
                    reason = result["metadata"].get("reason", "Data incomplete")

                    if suggested_action:
                        print(f"[EXECUTION_ENGINE] 📊 Step {i+1} succeeded but data incomplete: {reason}")
                        print(f"[EXECUTION_ENGINE] 🔄 Creating follow-up task: {suggested_action}")

                        # Create follow-up task
                        follow_up = self._create_follow_up_task(
                            original_subtask=subtask,
                            result=result,
                            suggested_action=suggested_action,
                            reason=reason
                        )

                        if follow_up:
                            # Insert follow-up task after current step
                            print(f"[EXECUTION_ENGINE] ✅ Added follow-up task: {follow_up['description']}")
                            subtasks.insert(i+1, follow_up)

                results.append(result)

                # Update accumulated data
                extracted_outputs = resolver.extract_outputs(
                    tool_name=tool_name,
                    raw_result=result["data"]
                )

                step_name = f"step_{i}_{tool_name}"
                context.add_result(step_name, tool_name, result, extracted_outputs)

                i += 1

        return results

    def _identify_parallel_group(self, subtasks: List[Dict[str, Any]], start_idx: int, accumulated_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify which subtasks can run in parallel starting from start_idx.

        Args:
            subtasks: All subtasks
            start_idx: Starting index to check from
            accumulated_data: Current accumulated data

        Returns:
            List of dicts: [{"index": i, "subtask": subtask}, ...]
        """
        parallel_group = []

        # Check if we have a pattern of navigation + extraction that can be parallelized
        if start_idx + 1 < len(subtasks):
            current = subtasks[start_idx]
            next_one = subtasks[start_idx + 1]

            # Pattern: playwright_execute + chart_extractor = can run in parallel
            if (current["tool"] == "playwright_execute" and
                next_one["tool"] == "chart_extractor"):

                # Find all such pairs in the remaining subtasks
                idx = start_idx
                while idx + 1 < len(subtasks):
                    nav_task = subtasks[idx]
                    extract_task = subtasks[idx + 1]

                    if (nav_task["tool"] == "playwright_execute" and
                        extract_task["tool"] == "chart_extractor"):

                        parallel_group.append({"index": idx, "subtask": nav_task})
                        parallel_group.append({"index": idx + 1, "subtask": extract_task})
                        idx += 2  # Skip both tasks
                    else:
                        break  # Pattern broken

                if len(parallel_group) >= 4:  # At least 2 pairs (4 tasks)
                    print(f"[EXECUTION_ENGINE] 🎯 Found {len(parallel_group)//2} navigation+extraction pairs that can run in parallel")
                    return parallel_group

        # Fallback: single task
        return [{"index": start_idx, "subtask": subtasks[start_idx]}]

    def _execute_parallel_subtasks(
        self,
        parallel_group: List[Dict[str, Any]],
        accumulated_data: Dict[str, Any],
        resolver: Any,
        plan: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple subtasks in true parallel using asyncio.gather().

        Args:
            parallel_group: List of {"index": i, "subtask": subtask} dicts
            accumulated_data: Current accumulated data
            resolver: DataFlowResolver instance
            plan: Execution plan

        Returns:
            List of result dictionaries in same order as parallel_group
        """
        async def execute_single_async(subtask_info: Dict[str, Any]) -> Dict[str, Any]:
            """Async wrapper for single subtask execution."""
            subtask = subtask_info["subtask"]
            idx = subtask_info["index"]

            # Resolve parameters
            resolved_params = resolver.resolve_inputs(
                tool_name=subtask["tool"],
                provided_params=subtask["parameters"],
                accumulated_data=accumulated_data,
                subtask_context={"subtask_index": idx + 1}
            )

            # Update subtask with resolved parameters
            subtask["parameters"] = resolved_params

            # Find executor
            executor = self._find_executor_for_tool(subtask["tool"])
            if not executor:
                return {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": False,
                    "error": f"No executor available for {subtask['tool']}"
                }

            # Create task
            from src.agents.base_agent import AgentTask, TaskPriority
            task = AgentTask(
                task_type=subtask["tool"],
                description=subtask["description"],
                parameters=subtask["parameters"],
                priority=TaskPriority.HIGH
            )

            # Execute
            try:
                result = executor.execute(task)
                print(f"[EXECUTION_ENGINE] ✓ Parallel subtask {idx+1}: {subtask['tool']} - {result.success}")

                return {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": result.success,
                    "data": result.data,
                    "metadata": result.metadata
                }

            except Exception as e:
                print(f"[EXECUTION_ENGINE] ❌ Parallel subtask {idx+1} failed: {e}")
                return {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": False,
                    "error": str(e)
                }

        async def execute_all_parallel() -> List[Dict[str, Any] | BaseException]:
            """Execute all subtasks in parallel."""
            tasks = [execute_single_async(info) for info in parallel_group]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Run parallel execution
        try:
            # Create new event loop for parallel execution
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                parallel_results = loop.run_until_complete(execute_all_parallel())
            finally:
                loop.close()

            # Handle any exceptions that occurred
            clean_results = []
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    print(f"[EXECUTION_ENGINE] ⚠️ Parallel task {i} raised exception: {result}")
                    # Create error result
                    subtask_info = parallel_group[i]
                    clean_results.append({
                        "subtask_id": subtask_info["subtask"]["subtask_id"],
                        "tool": subtask_info["subtask"]["tool"],
                        "success": False,
                        "error": str(result)
                    })
                else:
                    clean_results.append(result)

            return clean_results

        except Exception as e:
            print(f"[EXECUTION_ENGINE] ❌ Parallel execution failed: {e}")
            import traceback
            traceback.print_exc()

            # Fallback: execute sequentially
            print("[EXECUTION_ENGINE] 🔄 Falling back to sequential execution")
            fallback_results = []
            for subtask_info in parallel_group:
                result = self._execute_single_subtask(
                    subtask_info["subtask"],
                    subtask_info["index"],
                    accumulated_data,
                    resolver,
                    plan
                )
                fallback_results.append(result)

            return fallback_results

    def _execute_single_subtask(
        self,
        subtask: Dict[str, Any],
        idx: int,
        accumulated_data: Dict[str, Any],
        resolver: Any,
        plan: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a single subtask.

        Args:
            subtask: Subtask to execute
            idx: Subtask index
            accumulated_data: Current accumulated data
            resolver: DataFlowResolver instance
            plan: Execution plan

        Returns:
            Result dictionary
        """
        tool_name = subtask["tool"]

        # Automatic input resolution
        resolved_params = resolver.resolve_inputs(
            tool_name=tool_name,
            provided_params=subtask["parameters"],
            accumulated_data=accumulated_data,
            subtask_context={"subtask_index": idx + 1}
        )

        subtask["parameters"] = resolved_params

        # Find executor
        executor = self._find_executor_for_tool(subtask["tool"])

        if not executor:
            print(f"[EXECUTION_ENGINE] ERROR: No executor found for tool: {subtask['tool']}")
            return {
                "subtask_id": subtask["subtask_id"],
                "tool": subtask["tool"],
                "success": False,
                "error": f"No executor available for {subtask['tool']}"
            }

        # Create and execute task
        from src.agents.base_agent import AgentTask, TaskPriority
        task = AgentTask(
            task_type=subtask["tool"],
            description=subtask["description"],
            parameters=subtask["parameters"],
            priority=TaskPriority.HIGH
        )

        try:
            result = executor.execute(task)
            print(f"[EXECUTION_ENGINE] ✓ Subtask {idx+1}: {tool_name} - {result.success}")

            return {
                "subtask_id": subtask["subtask_id"],
                "tool": subtask["tool"],
                "success": result.success,
                "data": result.data,
                "metadata": result.metadata
            }

        except Exception as e:
            print(f"[EXECUTION_ENGINE] ❌ Subtask {idx+1} failed: {e}")
            return {
                "subtask_id": subtask["subtask_id"],
                "tool": subtask["tool"],
                "success": False,
                "error": str(e)
            }

    def _find_executor_for_tool(self, tool_name: str) -> Optional[Any]:
        """
        Find an executor agent that can handle the specified tool.

        Args:
            tool_name: Name of the tool needed

        Returns:
            ExecutorAgent instance or None
        """
        for executor in self.executor_agents:
            # Check if executor has this tool
            if hasattr(executor, 'get_tool') and executor.get_tool(tool_name):
                return executor

        # If no exact match, return first executor
        return self.executor_agents[0] if self.executor_agents else None

    def _validate_step_success(
        self,
        subtask: Dict[str, Any],
        result: Any,
        accumulated_data: Dict[str, Any],
        plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate if a step actually succeeded in its goal.

        Args:
            subtask: The subtask that was executed
            result: Result from tool execution
            accumulated_data: All data from previous steps
            plan: Optional plan context

        Returns:
            Validation result dict
        """
        tool_name = subtask["tool"]
        result_data = result.data if hasattr(result, 'data') else result

        # Navigation validation (playwright_execute)
        if tool_name == "playwright_execute":
            method = subtask["parameters"].get("method", "")

            if method == "goto":
                # Check if navigation succeeded
                if not result_data or (isinstance(result_data, str) and "error" in result_data.lower()):
                    return {
                        "valid": False,
                        "reason": "Navigation failed or page didn't load",
                        "needs_replan": True
                    }

            elif method == "click":
                # Check if click led somewhere or triggered action
                if not result_data:
                    return {
                        "valid": False,
                        "reason": "Click action produced no result",
                        "needs_replan": True
                    }

        # Extraction validation (chart_extractor)
        elif tool_name == "chart_extractor":
            required_fields = plan.get("required_fields", []) if plan else []

            # Check if extraction got data
            if not result_data or (isinstance(result_data, list) and len(result_data) == 0):
                return {
                    "valid": False,
                    "reason": "Extraction returned no data - wrong page or empty content",
                    "needs_replan": True
                }

            # Check if extracted data has required fields
            if required_fields and isinstance(result_data, list) and len(result_data) > 0:
                first_record = result_data[0]
                if isinstance(first_record, dict):
                    present_fields = set(first_record.keys())
                    required_set = set(required_fields)
                    missing = required_set - present_fields

                    if len(missing) > len(required_fields) * 0.7:  # More than 70% fields missing
                        return {
                            "valid": False,
                            "reason": f"Extracted wrong data type - missing {len(missing)}/{len(required_fields)} fields",
                            "needs_replan": True
                        }

        # All checks passed
        return {
            "valid": True,
            "reason": "Step completed successfully",
            "needs_replan": False
        }

    def _dynamic_replan(
        self,
        original_task_desc: str,
        failed_step: Dict[str, Any],
        validation_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Re-invoke comprehensive analysis to create new execution steps.

        Args:
            original_task_desc: Original user request
            failed_step: The step that failed validation
            validation_result: Validation failure details
            context: Execution context including previous attempts

        Returns:
            List of new subtasks or empty list if re-planning fails
        """
        if not self.llm_service:
            print("[EXECUTION_ENGINE] No LLM service for re-planning")
            return []

        # Build re-planning prompt
        prompt = f"""A task execution step failed validation. Analyze why and create alternative steps.

Original Task: "{original_task_desc}"

Failed Step:
- Tool: {failed_step['tool']}
- Description: {failed_step.get('description', '')}
- Parameters: {json.dumps(failed_step.get('parameters', {}))}

Failure Reason: {validation_result['reason']}

Previous Attempts:
{json.dumps(context.get('previous_attempt', {}), indent=2)}

Create alternative steps to accomplish the original task. Consider:
1. Did we visit the wrong page? (e.g., listing instead of detail page)
2. Do we need to navigate deeper? (e.g., click "Showtimes" link)
3. Should we try a different source/URL?
4. Do we need intermediate navigation steps?

Return JSON array of new steps:
[
  {{"tool": "tool_name", "parameters": {{}}, "description": "what this does"}}
]

RETURN ONLY VALID JSON ARRAY:"""

        try:
            print("[EXECUTION_ENGINE] 🔄 Re-planning with LLM...")
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content.strip()

            # Extract JSON array
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                new_steps_data = json.loads(json_match.group())

                # Convert to proper subtask format
                new_subtasks = []
                for idx, step_data in enumerate(new_steps_data):
                    subtask = {
                        "subtask_id": f"{failed_step['subtask_id']}_replan_{idx}",
                        "tool": step_data.get("tool", ""),
                        "parameters": step_data.get("parameters", {}),
                        "description": step_data.get("description", "")
                    }
                    new_subtasks.append(subtask)

                print(f"[EXECUTION_ENGINE] ✅ Re-planning generated {len(new_subtasks)} new steps")
                return new_subtasks
            else:
                print("[EXECUTION_ENGINE] ⚠️ Could not parse re-planning response")
                return []

        except Exception as e:
            print(f"[EXECUTION_ENGINE] ❌ Re-planning failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _create_follow_up_task(
        self,
        original_subtask: Dict[str, Any],
        result: Dict[str, Any],
        suggested_action: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a follow-up subtask when original task is incomplete.

        Args:
            original_subtask: The original subtask that was incomplete
            result: Result from the incomplete subtask
            suggested_action: Suggested action from completeness evaluation
            reason: Reason for incompleteness

        Returns:
            Follow-up subtask dict or None
        """
        try:
            original_tool = original_subtask["tool"]
            original_params = original_subtask["parameters"]

            # Create follow-up based on suggested action
            if suggested_action == "search_more_sources":
                # For searches, use LLM-based refinement
                original_query = original_params.get("query", "")

                if not original_query:
                    print(f"[EXECUTION_ENGINE] No query in parameters, cannot create follow-up")
                    return None

                # Use LLM to suggest alternative search terms
                if self.llm_service:
                    prompt = f"""Suggest an alternative search query for: "{original_query}"

The original search didn't find complete results. Suggest a different query that might work better.

Return ONLY the alternative query text (no quotes, no explanation):"""

                    try:
                        model = self.llm_service.get_model()
                        response = model.invoke(prompt)
                        alt_query = response.content.strip().strip('"')

                        if alt_query and alt_query != original_query:
                            follow_up = {
                                "subtask_id": f"{original_subtask['subtask_id']}_followup",
                                "tool": original_tool,
                                "parameters": {
                                    **original_params,
                                    "query": alt_query
                                },
                                "description": f"Try alternative search: {alt_query}"
                            }
                            return follow_up
                    except Exception as e:
                        print(f"[EXECUTION_ENGINE] LLM alternative query failed: {e}")

                # Fallback: just retry with same query
                return None

            elif suggested_action == "use_alternative_extraction":
                # Switch from playwright_execute to chart_extractor for better results
                print(f"[EXECUTION_ENGINE] 🔄 Switching to chart_extractor for more complete extraction")

                # Get the current URL (should be in accumulated data or plan context)
                current_url = original_params.get("url", "")

                # Get required fields from the plan
                required_fields = []
                if "required_fields" in original_params:
                    required_fields = original_params["required_fields"]

                follow_up = {
                    "subtask_id": f"{original_subtask['subtask_id']}_chart_extract",
                    "tool": "chart_extractor",
                    "parameters": {
                        "required_fields": required_fields,
                        "limit": 50  # Request more items
                    },
                    "description": f"Use chart_extractor for comprehensive extraction: {reason}"
                }
                return follow_up

            elif suggested_action == "extract_more_details":
                # For extraction, try to get missing fields
                follow_up = {
                    "subtask_id": f"{original_subtask['subtask_id']}_followup",
                    "tool": original_tool,
                    "parameters": {
                        **original_params,
                        "extract_all": True  # Request more comprehensive extraction
                    },
                    "description": f"Extract additional details: {reason}"
                }
                return follow_up

            elif suggested_action == "search_alternate_sources":
                # Try a different search source or approach
                original_query = original_params.get("query", "")
                if original_query:
                    # Add alternative search terms
                    alt_query = f"{original_query} alternative sources"
                    follow_up = {
                        "subtask_id": f"{original_subtask['subtask_id']}_followup",
                        "tool": original_tool,
                        "parameters": {
                            **original_params,
                            "query": alt_query
                        },
                        "description": f"Search alternate sources: {alt_query}"
                    }
                    return follow_up

            # Default: retry with same parameters
            print(f"[EXECUTION_ENGINE] No specific follow-up strategy for action: {suggested_action}")
            return None

        except Exception as e:
            print(f"[EXECUTION_ENGINE] Error creating follow-up task: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _plan_next_steps_adaptive(
        self,
        goal: str,
        current_results: List[Dict[str, Any]],
        accumulated_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Plan next steps incrementally based on current observation.

        Args:
            goal: Original goal
            current_results: Results so far
            accumulated_data: All accumulated data

        Returns:
            List of next subtasks (1-3 steps)
        """
        if not self.llm_service:
            print("[EXECUTION_ENGINE] No LLM service for incremental planning")
            return []

        # Build context from previous results
        results_summary = []
        for r in current_results[-3:]:  # Last 3 results
            results_summary.append({
                "tool": r.get("tool"),
                "success": r.get("success"),
                "description": r.get("description", "")[:100]
            })

        prompt = f"""Plan next 1-3 steps to achieve the goal based on current state.

Goal: "{goal}"

Previous Steps:
{json.dumps(results_summary, indent=2)}

Current State:
- Last tool: {current_results[-1].get('tool') if current_results else 'none'}
- Success: {current_results[-1].get('success') if current_results else False}
- Has data: {bool(current_results[-1].get('data') if current_results else False)}

**IMPORTANT**: If we're already at the target page, DON'T navigate again! Move to next action (click, fill, extract, etc.).

**CRITICAL: Tool Parameter Formats**

playwright_execute (MOST COMMON):
- REQUIRED: method (goto, click, fill, press, wait_for_timeout, text_content, etc.)
- Optional: selector (for click, fill, press)
- Optional: args (method-specific, e.g., {{"value": "text"}} for fill, {{"key": "Enter"}} for press)

Examples:
1. Fill search box:
   {{"tool": "playwright_execute", "parameters": {{"method": "fill", "selector": "input[name='q']", "args": {{"value": "OnePlus trimmer"}}}}, "description": "Search for OnePlus trimmer"}}

2. Press Enter:
   {{"tool": "playwright_execute", "parameters": {{"method": "press", "selector": "input[name='q']", "args": {{"key": "Enter"}}}}, "description": "Submit search"}}

3. Wait for page:
   {{"tool": "playwright_execute", "parameters": {{"method": "wait_for_timeout", "args": {{"timeout": 3000}}}}, "description": "Wait 3s for results"}}

4. Extract text:
   {{"tool": "playwright_execute", "parameters": {{"method": "text_content", "selector": "body"}}, "description": "Get page content"}}

chart_extractor:
- REQUIRED: required_fields (array of field names)
- Optional: limit (number of records)

Example:
{{"tool": "chart_extractor", "parameters": {{"required_fields": ["name", "price", "rating"], "limit": 10}}, "description": "Extract products"}}

What should we do next to achieve the goal?

Return JSON array of 1-3 next steps:
[
  {{"tool": "tool_name", "parameters": {{"method": "...", ...}}, "description": "what this does"}}
]

If goal is achieved, return empty array: []

RETURN ONLY VALID JSON ARRAY:"""

        try:
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content.strip()

            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                steps_data = json.loads(json_match.group())

                # Convert to subtask format
                next_subtasks = []
                base_id = f"adaptive_{int(time.time())}"

                for idx, step_data in enumerate(steps_data):
                    subtask = {
                        "subtask_id": f"{base_id}_step_{idx}",
                        "tool": step_data.get("tool", ""),
                        "parameters": step_data.get("parameters", {}),
                        "description": step_data.get("description", "")
                    }
                    next_subtasks.append(subtask)

                return next_subtasks

            return []

        except Exception as e:
            print(f"[EXECUTION_ENGINE] LLM incremental planning failed: {e}")
            return []

    def _get_data_flow_resolver(self) -> Any:
        """Get the DataFlowResolver instance."""
        from src.core.data_flow_resolver import get_resolver
        return get_resolver()
