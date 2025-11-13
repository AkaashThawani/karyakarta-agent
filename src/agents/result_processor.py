"""
Result Processor Component

Responsible for processing execution results, synthesizing final answers,
and determining goal achievement.
"""

from typing import List, Dict, Any, Optional
import json
import time


class ResultProcessor:
    """
    Component responsible for processing execution results and synthesizing answers.

    Handles:
    - Result synthesis and formatting
    - Goal achievement checking
    - Structured data extraction from results
    - Answer generation (LLM and fallback)
    """

    def __init__(self, llm_service: Any = None):
        """
        Initialize ResultProcessor.

        Args:
            llm_service: LLM service for synthesis
        """
        self.llm_service = llm_service
        self.structured_memory: Dict[str, Dict[str, Any]] = {}

    def synthesize_results(self, task_description: str, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesize results from multiple subtasks into final answer.

        Args:
            task_description: Original task description
            subtask_results: Results from subtasks

        Returns:
            Synthesized final result
        """
        # Extract and store structured data from successful results
        successful_results = [r for r in subtask_results if r.get("success") and r.get("data")]
        if successful_results:
            self._extract_structured_data(task_description, successful_results)

        # Create synthesis
        synthesis = {
            "task_description": task_description,
            "answer": self._generate_answer(task_description, subtask_results),
            "sources": [r["tool"] for r in subtask_results],
            "subtask_count": len(subtask_results)
        }

        return synthesis

    def _generate_answer(self, task_description: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate final answer from results using LLM synthesis.

        Uses the LLM to intelligently format and present results based on
        the user's original request (e.g., creating tables, comparisons, etc.)

        Args:
            task_description: Original task description
            results: Results to synthesize

        Returns:
            Final answer string formatted by LLM
        """
        # Collect successful results
        successful_results = [r for r in results if r.get("success") and r.get("data")]
        failed_results = [r for r in results if not r.get("success")]

        if not successful_results:
            error_msg = "I apologize, but I couldn't generate a complete answer from the tools.\n\n"
            if failed_results:
                error_msg += "**Errors encountered:**\n"
                for r in failed_results:
                    error_msg += f"- {r['tool']}: {r.get('error', 'Unknown error')}\n"
            return error_msg

        # Check for structured data first
        all_structured_data = []
        for result in successful_results:
            data = result.get("data")
            if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
                all_structured_data.extend(data)

        # If we found structured data, format it as markdown table
        if all_structured_data:
            print(f"[RESULT_PROCESSOR] ✅ Found {len(all_structured_data)} structured records, formatting as table")

            # Get all unique field names
            all_fields = set()
            for record in all_structured_data:
                all_fields.update(record.keys())

            # Sort fields for consistent column order
            fields = sorted(all_fields)

            # Create markdown table
            markdown = "| " + " | ".join(fields) + " |\n"
            markdown += "| " + " | ".join(["---" for _ in fields]) + " |\n"

            for record in all_structured_data:
                row_values = [str(record.get(field, "")) for field in fields]
                markdown += "| " + " | ".join(row_values) + " |\n"

            return markdown

        # Use LLM to synthesize results intelligently
        print("[RESULT_PROCESSOR] Using LLM to synthesize final answer...")
        self.log("Using LLM to synthesize final answer...")

        # Check if LLM service is available
        if not self.llm_service:
            print("[RESULT_PROCESSOR] No LLM service available, using fallback")
            return self._fallback_answer(task_description, successful_results, failed_results)

        try:
            # Build context for LLM
            synthesis_prompt = self._build_synthesis_prompt(task_description, successful_results)

            # Get LLM model and invoke it
            model = self.llm_service.get_model()
            response = model.invoke(synthesis_prompt)

            # Extract content from response
            synthesized_answer = response.content.strip() if hasattr(response, 'content') else str(response).strip()

            if synthesized_answer and len(synthesized_answer) > 0:
                print(f"[RESULT_PROCESSOR] LLM synthesis complete ({len(synthesized_answer)} chars)")
                return synthesized_answer
            else:
                print("[RESULT_PROCESSOR] ⚠️ LLM returned empty response, using fallback")
                return self._fallback_answer(task_description, successful_results, failed_results)

        except Exception as e:
            print(f"[RESULT_PROCESSOR] LLM synthesis failed: {e}, using fallback")
            return self._fallback_answer(task_description, successful_results, failed_results)

    def _build_synthesis_prompt(self, task_description: str, results: List[Dict[str, Any]]) -> str:
        """
        Build prompt for LLM to synthesize results.
        Includes conversation history and structured memory for context-aware responses.

        Args:
            task_description: Original task description
            results: Successful tool results

        Returns:
            Prompt string for LLM
        """
        prompt = f"""You are a helpful assistant that presents information clearly and concisely.

**IMPORTANT: All subtasks have completed successfully. Provide a complete, final answer.**

"""

        # Include structured memory if available
        if self.structured_memory:
            prompt += "**Previously Extracted Data (use this for comparisons):**\n"
            for subject, data in self.structured_memory.items():
                prompt += f"\n{subject}:\n"
                # Include key fields
                for key, value in data.items():
                    if key not in ["timestamp", "query"]:  # Skip metadata
                        prompt += f"  - {key}: {value}\n"
            prompt += "\n"

        prompt += f"""**Current Request:** {task_description}

I have gathered the following information from various tools:

"""

        # Limit to top 10 results to avoid token limits
        limited_results = results[:10]
        if len(results) > 10:
            print(f"[RESULT_PROCESSOR] 📊 Limiting synthesis to top 10 results (have {len(results)} total)")

        for i, result in enumerate(limited_results, 1):
            tool_name = result["tool"].replace("_", " ").title()
            data = result["data"]

            prompt += f"--- {tool_name} Results ---\n"

            # Truncate very long data
            if isinstance(data, str) and len(data) > 3000:
                prompt += f"{data[:3000]}...\n[Content truncated for processing]\n\n"
            else:
                prompt += f"{data}\n\n"

        prompt += f"""---

Based on the information above, please provide a comprehensive answer to the user's request: "{task_description}"

Important:
- If the user asked for a table/comparison, create a clear markdown table
- If the user asked for a list, provide a well-organized list
- Present the information in the format the user requested
- Be concise but complete
- Use markdown formatting for better readability

Your response:"""

        return prompt

    def _fallback_answer(self, task_description: str, successful_results: List[Dict[str, Any]], failed_results: List[Dict[str, Any]]) -> str:
        """
        Fallback answer generation without LLM (simple formatting).

        Args:
            task_description: Original task description
            successful_results: Successful tool results
            failed_results: Failed tool results

        Returns:
            Formatted answer string
        """
        # Simple formatting fallback
        answer = f"# Results for: {task_description}\n\n"

        for i, result in enumerate(successful_results, 1):
            data = result["data"]
            tool = result["tool"]
            tool_display = tool.replace("_", " ").title()

            answer += f"## {i}. {tool_display}\n\n"

            # Format based on data type
            if isinstance(data, str):
                if len(data) > 500:
                    answer += f"{data[:500]}...\n\n"
                    answer += f"*[Truncated for readability. Full length: {len(data)} characters]*\n\n"
                else:
                    answer += f"{data}\n\n"
            elif isinstance(data, dict):
                answer += "```json\n"
                answer += json.dumps(data, indent=2)
                answer += "\n```\n\n"
            elif isinstance(data, list):
                answer += "**Key Points:**\n"
                for item in data[:5]:
                    answer += f"- {item}\n"
                if len(data) > 5:
                    answer += f"\n*...and {len(data) - 5} more items*\n"
                answer += "\n"
            else:
                answer += f"{str(data)}\n\n"

        # Add summary
        if len(successful_results) > 1:
            answer += "---\n\n"
            answer += f"**Summary**: Successfully executed {len(successful_results)} tools"
            if failed_results:
                answer += f" ({len(failed_results)} failed)"
            answer += "\n"

        return answer

    def check_goal_achieved(self, results: List[Dict[str, Any]], goal: str, plan: Optional[Dict[str, Any]]) -> bool:
        """
        Check if goal achieved using existing completeness infrastructure.
        ZERO HARDCODING - delegates to ResultValidator and completeness checks.

        Args:
            results: Execution results so far
            goal: Original goal
            plan: Execution plan

        Returns:
            True if goal achieved
        """
        # Safety: Prevent infinite loops
        if len(results) >= 8:
            print(f"[RESULT_PROCESSOR] ⚠️ Reached result limit (8), considering goal achieved")
            return True

        # Get required fields from plan
        required_fields = plan.get("required_fields", []) if plan else []

        # Collect all successful results with data
        successful_with_data = [
            r for r in results
            if r.get("success") and r.get("data")
        ]

        if not successful_with_data:
            print(f"[RESULT_PROCESSOR] No successful results with data yet")
            return False

        # SPECIAL HANDLING FOR ADAPTIVE TASKS
        # For adaptive tasks, don't consider search results as goal achievement
        task_type = plan.get("task_structure", {}).get("type", "sequential") if plan else "sequential"
        if task_type == "adaptive":
            return self._check_adaptive_goal_achieved(results, goal, plan)

        # If we have required fields, use existing ResultValidator
        if required_fields:
            try:
                from src.routing.result_validator import ResultValidator

                # Extract data from results
                all_data = []
                for r in successful_with_data:
                    data = r.get("data")
                    if isinstance(data, list):
                        all_data.extend(data)
                    elif isinstance(data, dict):
                        all_data.append(data)

                if all_data:
                    validator = ResultValidator()
                    validation = validator.validate(
                        all_data,
                        required_fields,
                        None
                    )

                    is_complete = validation.get("complete", False)
                    coverage = validation.get("coverage", 0.0)

                    if is_complete:
                        print(f"[RESULT_PROCESSOR] ✅ Goal achieved: data complete (coverage: {coverage*100:.0f}%)")
                        return True
                    else:
                        print(f"[RESULT_PROCESSOR] Goal not achieved: coverage {coverage*100:.0f}%, missing {validation.get('missing_fields')}")
                        return False
            except Exception as e:
                print(f"[RESULT_PROCESSOR] Completeness check failed: {e}")

        # Fallback: Check if we have substantial data
        last_result = results[-1]

        # Check if last result has completeness metadata from executor
        if last_result.get("metadata", {}).get("complete") is not None:
            is_complete = last_result["metadata"].get("complete", False)
            if is_complete:
                print(f"[RESULT_PROCESSOR] ✅ Goal achieved: executor marked as complete")
                return True

        # Check if we have meaningful data
        has_meaningful_data = (
            last_result.get("success") and
            last_result.get("data") and
            len(str(last_result.get("data"))) > 100
        )

        if has_meaningful_data:
            print(f"[RESULT_PROCESSOR] ✅ Goal achieved: has meaningful data")
            return True

        return False

    def _check_adaptive_goal_achieved(self, results: List[Dict[str, Any]], goal: str, plan: Optional[Dict[str, Any]]) -> bool:
        """
        Special goal achievement check for adaptive tasks.
        For adaptive tasks, we need to actually perform the interactive actions,
        not just find information about the target.

        Args:
            results: Execution results so far
            goal: Original goal
            plan: Execution plan

        Returns:
            True if adaptive goal is actually achieved
        """
        print(f"[RESULT_PROCESSOR] 🔍 Checking adaptive goal achievement for: {goal}")

        # Get successful playwright_execute results (actual interactions)
        playwright_results = [
            r for r in results
            if r.get("success") and r.get("tool") == "playwright_execute"
        ]

        if not playwright_results:
            print(f"[RESULT_PROCESSOR] No successful playwright interactions yet")
            return False

        # Analyze the goal to understand what actual interactions are needed
        goal_lower = goal.lower()

        # For flight search tasks
        if any(word in goal_lower for word in ["flight", "flights", "book flight", "search flight"]):
            return self._check_flight_search_goal(results, goal)

        # For general "go to X and do Y" tasks
        elif any(word in goal_lower for word in ["go to", "navigate to", "visit"]):
            return self._check_navigation_goal(results, goal, plan)

        # For form filling tasks
        elif any(word in goal_lower for word in ["fill", "enter", "type", "search for"]):
            return self._check_form_filling_goal(results, goal)

        # Default: check if we have meaningful interactions beyond just navigation
        navigation_count = sum(1 for r in playwright_results
                             if r.get("parameters", {}).get("method") == "goto")
        interaction_count = len(playwright_results) - navigation_count

        # Need at least 2 interactions (navigation + something else) for adaptive tasks
        if interaction_count >= 2:
            print(f"[RESULT_PROCESSOR] ✅ Adaptive goal achieved: {interaction_count} interactions performed")
            return True
        else:
            print(f"[RESULT_PROCESSOR] Adaptive goal not achieved: only {interaction_count} interactions (need 2+)")
            return False

    def _check_flight_search_goal(self, results: List[Dict[str, Any]], goal: str) -> bool:
        """
        Check if flight search goal is achieved.
        Need to: navigate to flight site + fill departure + fill destination + select dates + search
        """
        playwright_results = [
            r for r in results
            if r.get("success") and r.get("tool") == "playwright_execute"
        ]

        # Count different types of interactions
        goto_count = sum(1 for r in playwright_results
                        if r.get("parameters", {}).get("method") == "goto")
        fill_count = sum(1 for r in playwright_results
                        if r.get("parameters", {}).get("method") == "fill")
        click_count = sum(1 for r in playwright_results
                         if r.get("parameters", {}).get("method") == "click")

        print(f"[RESULT_PROCESSOR] Flight search progress: goto={goto_count}, fill={fill_count}, click={click_count}")

        # For flight search, we typically need:
        # 1. Navigate to flight site
        # 2. Fill departure city
        # 3. Fill destination city
        # 4. Select dates (could be fill or click)
        # 5. Click search button

        # Consider achieved if we have navigation + at least 2 fills + 1 click
        if goto_count >= 1 and fill_count >= 2 and click_count >= 1:
            print(f"[RESULT_PROCESSOR] ✅ Flight search goal achieved: navigated and performed search")
            return True
        else:
            print(f"[RESULT_PROCESSOR] Flight search goal not achieved: missing interactions")
            return False

    def _check_navigation_goal(self, results: List[Dict[str, Any]], goal: str, plan: Optional[Dict[str, Any]]) -> bool:
        """
        Check if navigation goal is achieved.
        For "go to X and do Y" tasks, need to navigate AND perform the action.
        """
        playwright_results = [
            r for r in results
            if r.get("success") and r.get("tool") == "playwright_execute"
        ]

        # Must have navigated somewhere
        goto_results = [r for r in playwright_results
                       if r.get("parameters", {}).get("method") == "goto"]

        if not goto_results:
            print(f"[RESULT_PROCESSOR] Navigation goal not achieved: no navigation performed")
            return False

        # Check what action was supposed to be performed
        goal_lower = goal.lower()

        if "search" in goal_lower:
            # Need navigation + search action (fill + click)
            fill_count = sum(1 for r in playwright_results
                           if r.get("parameters", {}).get("method") == "fill")
            click_count = sum(1 for r in playwright_results
                            if r.get("parameters", {}).get("method") == "click")

            if fill_count >= 1 and click_count >= 1:
                print(f"[RESULT_PROCESSOR] ✅ Navigation + search goal achieved")
                return True

        elif "fill" in goal_lower or "enter" in goal_lower:
            # Need navigation + form filling
            fill_count = sum(1 for r in playwright_results
                           if r.get("parameters", {}).get("method") == "fill")

            if fill_count >= 1:
                print(f"[RESULT_PROCESSOR] ✅ Navigation + form filling goal achieved")
                return True

        elif "click" in goal_lower:
            # Need navigation + clicking
            click_count = sum(1 for r in playwright_results
                            if r.get("parameters", {}).get("method") == "click")

            # Subtract goto clicks if any
            actual_clicks = click_count - len(goto_results)

            if actual_clicks >= 1:
                print(f"[RESULT_PROCESSOR] ✅ Navigation + click goal achieved")
                return True

        # Default: if we have navigation + any other interaction, consider achieved
        total_interactions = len(playwright_results)
        if total_interactions >= 2:
            print(f"[RESULT_PROCESSOR] ✅ Navigation goal achieved: {total_interactions} interactions")
            return True

        print(f"[RESULT_PROCESSOR] Navigation goal not achieved: missing required actions")
        return False

    def _check_form_filling_goal(self, results: List[Dict[str, Any]], goal: str) -> bool:
        """
        Check if form filling goal is achieved.
        Need to navigate to form and actually fill fields.
        """
        playwright_results = [
            r for r in results
            if r.get("success") and r.get("tool") == "playwright_execute"
        ]

        goto_count = sum(1 for r in playwright_results
                        if r.get("parameters", {}).get("method") == "goto")
        fill_count = sum(1 for r in playwright_results
                        if r.get("parameters", {}).get("method") == "fill")

        # Need navigation + at least one fill action
        if goto_count >= 1 and fill_count >= 1:
            print(f"[RESULT_PROCESSOR] ✅ Form filling goal achieved: navigated and filled {fill_count} fields")
            return True
        else:
            print(f"[RESULT_PROCESSOR] Form filling goal not achieved: goto={goto_count}, fill={fill_count}")
            return False

    def _extract_structured_data(self, task_description: str, results: List[Dict[str, Any]]) -> None:
        """
        Extract and store structured data from results for future reference.
        Uses LLM to identify and extract key information.

        Args:
            task_description: Description of what was queried
            results: Successful tool results
        """
        try:
            if not self.llm_service or not results:
                return

            # Build extraction prompt
            prompt = f"""Extract key structured data from the following results.

Task: {task_description}

Results:
"""
            for result in results:
                data = str(result.get("data", ""))[:1000]  # Limit length
                prompt += f"\n{data}\n"

            prompt += """
Extract and return ONLY a JSON object with key information like:
{
    "subject": "iPhone 17" or "Pixel 10" etc,
    "price": "$799",
    "colors": ["Blue", "Red"],
    "specs": {"display": "6.3 inch", "battery": "4700mAh"},
    "key_features": ["Feature 1", "Feature 2"]
}

If multiple items, use the subject name as the key.
Return ONLY valid JSON, no explanations.

JSON:"""

            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Parse JSON with error recovery
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()

                try:
                    extracted_data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[RESULT_PROCESSOR] JSON parse error: {e}, attempting to fix...")
                    # Try to fix common JSON issues
                    json_str = json_str.replace("'", '"')  # Single to double quotes
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
                    json_str = re.sub(r'(\w+):', r'"\1":', json_str)  # Quote unquoted keys

                    try:
                        extracted_data = json.loads(json_str)
                        print(f"[RESULT_PROCESSOR] JSON fixed and parsed successfully")
                    except:
                        print(f"[RESULT_PROCESSOR] Could not fix JSON, skipping structured data storage")
                        return

                # Store in structured memory with timestamp
                subject = extracted_data.get("subject", f"query_{len(self.structured_memory)}")
                self.structured_memory[subject] = {
                    **extracted_data,
                    "timestamp": time.time(),
                    "query": task_description
                }
                print(f"[RESULT_PROCESSOR] ✅ Stored structured data for: {subject}")

        except Exception as e:
            print(f"[RESULT_PROCESSOR] Failed to extract structured data: {e}")

    def log(self, message: str, level: str = "info") -> None:
        """
        Simple logging method.

        Args:
            message: Message to log
            level: Log level
        """
        print(f"[RESULT_PROCESSOR] {message}")
