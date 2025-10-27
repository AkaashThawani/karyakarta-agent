"""
Reason Agent - Planning and Coordination

The "brain" of the multi-agent system that analyzes tasks,
creates execution plans, and coordinates other agents.
"""

from typing import List, Dict, Any, Optional
from src.agents.base_agent import (
    BaseAgent, AgentTask, AgentResult, AgentMessage,
    MessageType, TaskPriority, AgentStatus
)
from src.prompts import get_reason_agent_prompt
import time
import json


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
        self.available_tools = available_tools
        self.executor_agents = executor_agents or []
        self.execution_history: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        
        # NEW: Conversation context for multi-turn awareness
        self.conversation_history: List[Dict[str, Any]] = []
        self.original_request: Optional[str] = None
        self.previous_results: List[Dict[str, Any]] = []
        
        # NEW: Tool descriptions for LLM-based selection
        self._tool_descriptions: Optional[Dict[str, str]] = None
        
        # NEW: Structured memory for preserving detailed data
        self.structured_memory: Dict[str, Dict[str, Any]] = {}
    
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
            # NEW: Store conversation context
            self.conversation_history.append({
                "role": "user",
                "content": task.description,
                "timestamp": time.time()
            })
            
            # Store original request if not set
            if not self.original_request:
                self.original_request = task.description
            
            # Update context
            if context:
                self.context.update(context)
            
            # Step 1: Analyze the task
            self.log("Step 1: Analyzing task requirements...")
            analysis = self._analyze_task(task)
            
            # Step 2: Create execution plan
            self.log("Step 2: Creating execution plan...")
            plan = self._create_plan(task, analysis)
            
            # Step 3: Determine if we need subtasks
            if plan.get("needs_delegation", False):
                self.log("Step 3: Task requires delegation to executors")
                subtasks = plan.get("subtasks", [])
                
                # Actually delegate to executor agents
                subtask_results = self._execute_delegation(subtasks)
                
                # Step 4: Synthesize results
                self.log("Step 4: Synthesizing results...")
                final_result = self._synthesize_results(task, subtask_results)
            else:
                self.log("Step 3: Task can be handled directly")
                final_result = self._handle_simple_task(task, analysis)
            
            execution_time = time.time() - start_time
            self.state.update_status(AgentStatus.COMPLETED)
            
            # NEW: Store result for future turns
            self.previous_results.append({
                "task": task.description,
                "result": final_result,
                "timestamp": time.time()
            })
            
            # Store assistant response in conversation history
            answer = final_result.get("answer", str(final_result))
            self.conversation_history.append({
                "role": "assistant",
                "content": answer,
                "timestamp": time.time()
            })
            
            # Keep only last 10 conversation turns to avoid memory overflow
            if len(self.conversation_history) > 20:  # 10 turns = 20 messages
                self.conversation_history = self.conversation_history[-20:]
            
            # Record in history
            self.execution_history.append({
                "task_id": task.task_id,
                "result": final_result,
                "execution_time": execution_time
            })
            
            return AgentResult.success_result(
                data=final_result,
                agent_id=self.agent_id,
                execution_time=execution_time,
                metadata={"plan": plan, "analysis": analysis}
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
    
    def _analyze_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Analyze task to understand requirements.
        
        Args:
            task: Task to analyze
            
        Returns:
            Analysis results
        """
        # Simple analysis - in full implementation, use LLM
        required_tools = self._identify_required_tools(task)
        
        analysis = {
            "task_type": task.task_type,
            "complexity": "simple" if len(task.parameters) <= 2 else "complex",
            "required_tools": required_tools,
            "estimated_steps": len(required_tools)
        }
        
        # Console debug output
        print(f"\n{'='*60}")
        print(f"[REASON] Task Analysis:")
        print(f"[REASON]   - Description: {task.description[:100]}...")
        print(f"[REASON]   - Identified {len(required_tools)} tools: {required_tools}")
        print(f"[REASON]   - Complexity: {analysis['complexity']}")
        print(f"{'='*60}\n")
        
        self.log(f"[REASON] Task Analysis:")
        self.log(f"[REASON]   - Description: {task.description[:100]}...")
        self.log(f"[REASON]   - Identified {len(required_tools)} tools: {required_tools}")
        self.log(f"[REASON]   - Complexity: {analysis['complexity']}")
        
        return analysis
    
    def _get_tool_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions of all available tools from executors.
        Cached after first call for performance.
        
        Returns:
            Dictionary mapping tool names to descriptions
        """
        if self._tool_descriptions is not None:
            return self._tool_descriptions
        
        descriptions = {}
        for executor in self.executor_agents:
            if hasattr(executor, 'tools'):
                for tool in executor.tools:
                    if hasattr(tool, 'name') and hasattr(tool, 'description'):
                        descriptions[tool.name] = tool.description
        
        self._tool_descriptions = descriptions
        print(f"[REASON] Loaded {len(descriptions)} tool descriptions")
        return descriptions
    
    def _llm_tool_selection(self, task: AgentTask) -> List[str]:
        """
        Use LLM to intelligently select tools based on descriptions.
        
        Args:
            task: Task to analyze
            
        Returns:
            List of selected tool names
        """
        tool_descriptions = self._get_tool_descriptions()
        
        if not tool_descriptions:
            print("[REASON] No tool descriptions available, using keyword fallback")
            return []
        
        # Build prompt for LLM
        prompt = f"""You are a task planning assistant. Given a user's request and available tools, select the appropriate tools needed.

Available Tools:
"""
        for name, desc in tool_descriptions.items():
            prompt += f"- {name}: {desc}\n"
        
        prompt += f"""
User Request: "{task.description}"

Select the tools needed to accomplish this request. Consider:
1. Search tools to find information
2. Browsing tools to visit websites
3. Extraction tools to get structured data
4. Analysis tools to process results

Return ONLY a JSON array of tool names in execution order, like:
["google_search", "browse_website", "extract_table"]

If unsure, default to ["google_search"].

JSON Response:"""
        
        try:
            print("[REASON] Using LLM for tool selection...")
            if not self.llm_service:
                print("[REASON] No LLM service available")
                return []
            
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            
            # Extract content
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                tools_json = json_match.group()
                tools = json.loads(tools_json)
                print(f"[REASON] LLM selected tools: {tools}")
                return tools
            else:
                print("[REASON] Could not parse LLM response, using fallback")
                return []
                
        except Exception as e:
            print(f"[REASON] LLM tool selection failed: {e}")
            return []
    
    def _identify_required_tools(self, task: AgentTask) -> List[str]:
        """
        Identify which tools are needed using LLM-based selection.
        Simple, intelligent, and works for any query type.
        
        Args:
            task: Task to analyze
            
        Returns:
            List of required tool names in execution order
        """
        print("[REASON] Using LLM-based tool selection...")
        tools = self._llm_tool_selection(task)
        
        # Default to search if LLM selection fails
        if not tools:
            print("[REASON] LLM selection failed, defaulting to google_search")
            return ["google_search"]
        
        return tools
    
    def _create_plan(self, task: AgentTask, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create execution plan based on analysis.
        
        Args:
            task: Task to plan for
            analysis: Task analysis
            
        Returns:
            Execution plan
        """
        required_tools = analysis.get("required_tools", [])
        complexity = analysis.get("complexity", "simple")
        
        plan = {
            "needs_delegation": len(required_tools) > 0,
            "complexity": complexity,
            "subtasks": []
        }
        
        # Create subtasks for each required tool with proper parameters
        for i, tool in enumerate(required_tools):
            # Map parameters based on tool type
            tool_params = self._map_parameters_for_tool(tool, task.parameters, task.description)
            
            subtask = {
                "subtask_id": f"{task.task_id}_sub_{i}",
                "tool": tool,
                "parameters": tool_params,
                "description": f"Use {tool} for: {task.description}"
            }
            plan["subtasks"].append(subtask)
        
        return plan
    
    def _map_parameters_for_tool(
        self,
        tool_name: str,
        base_params: Dict[str, Any],
        description: str
    ) -> Dict[str, Any]:
        """
        Map parameters correctly for each tool type.
        
        Args:
            tool_name: Name of the tool
            base_params: Base parameters from task
            description: Task description
            
        Returns:
            Properly mapped parameters for the tool
        """
        query = base_params.get("query", description)
        
        # Tool-specific parameter mapping
        if tool_name == "google_search":
            return {"query": query}
        
        elif tool_name == "browse_website":
            # URL will be provided by chaining from search results
            # If not chained, try to extract from description
            if "http" in description:
                start = description.find("http")
                end = description.find(" ", start)
                if end == -1:
                    end = len(description)
                url = description[start:end].strip()
                return {"url": url}
            # If no URL available, this will be handled by chaining
            return {"url": ""}  # Will be replaced by chaining
        
        elif tool_name == "calculator":
            # Extract mathematical expression
            return {"expression": query}
        
        elif tool_name == "extract_data":
            # Extract_data needs content from previous tool
            # Will be populated by chaining
            # Use "html" type (valid: json, html, xml, csv, table)
            return {
                "data_type": "html",  # Valid type for text extraction
                "content": "",  # Will be filled by chaining
                "path": ""  # Optional XPath selector
            }
        
        else:
            # Default: pass query parameter
            return {"query": query}
    
    def _execute_delegation(self, subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Actually delegate tasks to executor agents and get real results.
        Handles sequential dependencies between tasks.
        
        Args:
            subtasks: List of subtasks to delegate
            
        Returns:
            List of results from executors
        """
        results = []
        previous_result = None
        
        for i, subtask in enumerate(subtasks):
            print(f"\n[REASON] === Subtask {i+1}/{len(subtasks)}: {subtask['tool']} ===")
            print(f"[REASON] Initial params: {subtask['parameters']}")
            
            self.log(f"[REASON] === Subtask {i+1}/{len(subtasks)}: {subtask['tool']} ===")
            self.log(f"[REASON] Initial params: {subtask['parameters']}")
            
            # Update parameters based on previous result
            if previous_result and previous_result.get("success"):
                print(f"[REASON] Chaining from previous result (tool: {previous_result.get('tool')})")
                self.log(f"[REASON] Chaining from previous result (tool: {previous_result.get('tool')})")
                
                subtask["parameters"] = self._chain_parameters(
                    subtask["tool"],
                    subtask["parameters"],
                    previous_result
                )
                
                print(f"[REASON] After chaining params: {subtask['parameters']}")
                self.log(f"[REASON] After chaining params: {subtask['parameters']}")
            else:
                if previous_result:
                    print(f"[REASON] Previous result failed, not chaining")
                    self.log(f"[REASON] Previous result failed, not chaining")
                else:
                    print(f"[REASON] First subtask, no previous result")
                    self.log(f"[REASON] First subtask, no previous result")
            
            # Find executor agent that can handle this tool
            executor = self._find_executor_for_tool(subtask["tool"])
            
            if not executor:
                self.log(f"No executor found for tool: {subtask['tool']}", level="error")
                result_entry = {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": False,
                    "error": f"No executor available for {subtask['tool']}"
                }
                results.append(result_entry)
                previous_result = result_entry
                continue
            
            # Create AgentTask for the executor
            task = AgentTask(
                task_type=subtask["tool"],
                description=subtask["description"],
                parameters=subtask["parameters"],
                priority=TaskPriority.HIGH
            )
            
            # NEW: Build context to pass to executor
            execution_context = {
                "conversation_history": self.conversation_history,
                "original_request": self.original_request,
                "previous_results": self.previous_results,
                "current_subtask_index": i,
                "total_subtasks": len(subtasks)
            }
            
            # Execute through executor agent with context
            try:
                result = executor.execute(task, context=execution_context)
                
                result_entry = {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": result.success,
                    "data": result.data,
                    "metadata": result.metadata
                }
                results.append(result_entry)
                previous_result = result_entry
                
                self.log(f"Subtask completed: {subtask['tool']} - Success: {result.success}")
                
            except Exception as e:
                self.log(f"Error executing subtask {subtask['tool']}: {e}", level="error")
                result_entry = {
                    "subtask_id": subtask["subtask_id"],
                    "tool": subtask["tool"],
                    "success": False,
                    "error": str(e)
                }
                results.append(result_entry)
                previous_result = result_entry
        
        return results
    
    def _chain_parameters(
        self,
        tool_name: str,
        current_params: Dict[str, Any],
        previous_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Chain parameters from previous result to current tool.
        
        Args:
            tool_name: Current tool name
            current_params: Current parameters
            previous_result: Result from previous tool
            
        Returns:
            Updated parameters
        """
        # If browse_website follows search, use first URL from search
        if tool_name == "browse_website" and previous_result.get("tool") == "google_search":
            data = previous_result.get("data", "")
            
            # Better URL extraction - look for URLs with common TLDs
            import re
            # Pattern to match URLs (simplified)
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, data)
            
            if urls:
                # Filter out common non-content URLs
                filtered_urls = [
                    url for url in urls 
                    if not any(skip in url.lower() for skip in [
                        'google.com', 'youtube.com', 'facebook.com',
                        'twitter.com', 'linkedin.com', 'instagram.com',
                        'example.com', 'wikipedia.org/wiki/Main_Page'
                    ])
                ]
                
                # Use first filtered URL or first URL if no filter matches
                selected_url = filtered_urls[0] if filtered_urls else urls[0]
                # Clean up URL (remove trailing punctuation)
                selected_url = selected_url.rstrip('.,;:!?')
                
                current_params["url"] = selected_url
                self.log(f"Chained URL from search: {selected_url}")
            else:
                self.log("No URL found in search results", level="warning")
        
        # If extract_data follows browse_website, use scraped content
        elif tool_name == "extract_data" and previous_result.get("tool") == "browse_website":
            data = previous_result.get("data", "")
            if data:
                current_params["content"] = data
                # Use "html" type - valid for extract_data (json, html, xml, csv, table)
                current_params["data_type"] = "html"
                self.log(f"Chained content from browse ({len(data)} chars)")
            else:
                self.log("No content from browse_website", level="warning")
        
        # If extract_data follows google_search (no browse in between), use search results
        elif tool_name == "extract_data" and previous_result.get("tool") == "google_search":
            data = previous_result.get("data", "")
            if data:
                current_params["content"] = data
                # Use "html" type for text content
                current_params["data_type"] = "html"
                self.log(f"Chained content from search ({len(data)} chars)")
            else:
                self.log("No content from google_search", level="warning")
        
        return current_params
    
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
        
        # If no exact match, return first executor (they can handle any tool they have)
        return self.executor_agents[0] if self.executor_agents else None
    
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
            
            # Parse JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group())
                
                # Store in structured memory with timestamp
                subject = extracted_data.get("subject", f"query_{len(self.structured_memory)}")
                self.structured_memory[subject] = {
                    **extracted_data,
                    "timestamp": time.time(),
                    "query": task_description
                }
                print(f"[REASON] Stored structured data for: {subject}")
                
        except Exception as e:
            print(f"[REASON] Failed to extract structured data: {e}")
    
    def _synthesize_results(self, task: AgentTask, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesize results from multiple subtasks into final answer.
        
        Args:
            task: Original task
            subtask_results: Results from subtasks
            
        Returns:
            Synthesized final result
        """
        # Extract and store structured data from successful results
        successful_results = [r for r in subtask_results if r.get("success") and r.get("data")]
        if successful_results:
            self._extract_structured_data(task.description, successful_results)
        
        # In full implementation, use LLM to synthesize
        synthesis = {
            "task_id": task.task_id,
            "description": task.description,
            "answer": self._generate_answer(task, subtask_results),
            "sources": [r["tool"] for r in subtask_results],
            "subtask_count": len(subtask_results)
        }
        
        return synthesis
    
    def _generate_answer(self, task: AgentTask, results: List[Dict[str, Any]]) -> str:
        """
        Generate final answer from results using LLM synthesis.
        
        Uses the LLM to intelligently format and present results based on
        the user's original request (e.g., creating tables, comparisons, etc.)
        
        Args:
            task: Original task
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
        
        # Use LLM to synthesize results intelligently
        print("[REASON] Using LLM to synthesize final answer...")
        self.log("Using LLM to synthesize final answer...")
        
        # Check if LLM service is available
        if not self.llm_service:
            print("[REASON] No LLM service available, using fallback")
            return self._fallback_answer(task, successful_results, failed_results)
        
        try:
            # Build context for LLM
            synthesis_prompt = self._build_synthesis_prompt(task, successful_results)
            
            # Get LLM model and invoke it (LangChain)
            model = self.llm_service.get_model()
            response = model.invoke(synthesis_prompt)
            
            # Extract content from LangChain response
            synthesized_answer = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            if synthesized_answer:
                print(f"[REASON] LLM synthesis complete ({len(synthesized_answer)} chars)")
                return synthesized_answer
            else:
                print("[REASON] LLM synthesis returned empty, using fallback")
                return self._fallback_answer(task, successful_results, failed_results)
                
        except Exception as e:
            print(f"[REASON] LLM synthesis failed: {e}, using fallback")
            self.log(f"LLM synthesis failed: {e}, using fallback", level="warning")
            return self._fallback_answer(task, successful_results, failed_results)
    
    def _build_synthesis_prompt(self, task: AgentTask, results: List[Dict[str, Any]]) -> str:
        """
        Build prompt for LLM to synthesize results.
        Includes conversation history and structured memory for context-aware responses.
        
        Args:
            task: Original task
            results: Successful tool results
            
        Returns:
            Prompt string for LLM
        """
        prompt = f"""You are a helpful assistant that presents information clearly and concisely.

"""
        
        # NEW: Include structured memory if available
        if self.structured_memory:
            prompt += "**Previously Extracted Data (use this for comparisons):**\n"
            for subject, data in self.structured_memory.items():
                prompt += f"\n{subject}:\n"
                # Include key fields
                for key, value in data.items():
                    if key not in ["timestamp", "query"]:  # Skip metadata
                        prompt += f"  - {key}: {value}\n"
            prompt += "\n"
        
        # Include conversation history for context
        if len(self.conversation_history) > 2:  # More than just current turn
            prompt += "**Conversation History:**\n"
            # Show last few turns (excluding current one)
            recent_history = self.conversation_history[:-1][-6:]  # Last 3 turns (6 messages)
            for msg in recent_history:
                role = msg["role"].capitalize()
                content = msg["content"][:200]  # Truncate long messages
                prompt += f"{role}: {content}\n"
            prompt += "\n"
        
        prompt += f"""**Current Request:** {task.description}

I have gathered the following information from various tools:

"""
        
        for i, result in enumerate(results, 1):
            tool_name = result["tool"].replace("_", " ").title()
            data = result["data"]
            
            prompt += f"--- {tool_name} Results ---\n"
            
            # Truncate very long data
            if isinstance(data, str) and len(data) > 3000:
                prompt += f"{data[:3000]}...\n[Content truncated for processing]\n\n"
            else:
                prompt += f"{data}\n\n"
        
        prompt += f"""---

Based on the information above, please provide a comprehensive answer to the user's request: "{task.description}"

Important:
- If the user asked for a table/comparison, create a clear markdown table
- If the user asked for a list, provide a well-organized list
- Present the information in the format the user requested
- Be concise but complete
- Use markdown formatting for better readability

Your response:"""
        
        return prompt
    
    def _fallback_answer(self, task: AgentTask, successful_results: List[Dict[str, Any]], failed_results: List[Dict[str, Any]]) -> str:
        """
        Fallback answer generation without LLM (simple formatting).
        
        Args:
            task: Original task
            successful_results: Successful tool results
            failed_results: Failed tool results
            
        Returns:
            Formatted answer string
        """
        # Simple formatting fallback
        answer = f"# Results for: {task.description}\n\n"
        
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
    
    def _handle_simple_task(self, task: AgentTask, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle simple task directly without delegation.
        
        Args:
            task: Task to handle
            analysis: Task analysis
            
        Returns:
            Direct result
        """
        return {
            "task_id": task.task_id,
            "description": task.description,
            "answer": f"Direct answer for {task.task_type}",
            "method": "direct"
        }
    
    def create_plan(self, task: AgentTask) -> Dict[str, Any]:
        """
        Public method to create plan without execution.
        
        Args:
            task: Task to plan for
            
        Returns:
            Execution plan
        """
        analysis = self._analyze_task(task)
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
