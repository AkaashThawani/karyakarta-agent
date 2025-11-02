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
from src.routing.task_decomposer import create_decomposer
from src.core.data_flow_resolver import get_resolver
from datetime import datetime
import time
import json
import asyncio


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
        
        # NEW: LLM-based task decomposer
        self.task_decomposer = create_decomposer(llm_service)
    
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
                
                # FIX 3: Populate memory from context
                if "conversation_history" in context:
                    self.conversation_history = context["conversation_history"]
                    print(f"[REASON] Loaded {len(self.conversation_history)} messages from context")
                
                if "previous_results" in context:
                    self.previous_results = context["previous_results"]
                    print(f"[REASON] Loaded {len(self.previous_results)} previous results")
                
                if "original_request" in context:
                    self.original_request = context["original_request"]
            
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
                
                # Actually delegate to executor agents (pass plan for auto-extraction)
                subtask_results = self._execute_delegation(subtasks, plan)
                
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
        Analyze task comprehensively in a SINGLE LLM call.
        Replaces 4 separate LLM calls with 1 combined analysis.
        
        Args:
            task: Task to analyze
            
        Returns:
            Analysis results with all required information
        """
        # Use comprehensive analysis (1 LLM call instead of 4)
        comprehensive = self._analyze_task_comprehensive(task)
        
        if comprehensive:
            # Got analysis from LLM
            analysis = {
                "task_type": task.task_type,
                "detected_type": comprehensive.get("task_type", "general"),
                "complexity": "simple" if len(comprehensive.get("required_tools", [])) <= 2 else "complex",
                "required_tools": comprehensive.get("required_tools", []),
                "estimated_steps": len(comprehensive.get("required_tools", [])),
                "query_params": comprehensive.get("query_params", {}),
                "required_fields": comprehensive.get("required_fields", []),
                "task_structure": comprehensive.get("task_structure", {"type": "single"})
            }
        else:
            # Fallback to simple analysis if LLM fails
            required_tools = self._identify_required_tools(task)
            analysis = {
                "task_type": task.task_type,
                "detected_type": "general",
                "complexity": "simple" if len(task.parameters) <= 2 else "complex",
                "required_tools": required_tools,
                "estimated_steps": len(required_tools),
                "query_params": {},
                "required_fields": [],
                "task_structure": {"type": "single"}
            }
        
        self.log(f"Task analysis complete: {len(analysis['required_tools'])} tools identified")
        
        return analysis
    
    def _analyze_task_comprehensive(self, task: AgentTask) -> Optional[Dict[str, Any]]:
        """
        SINGLE comprehensive LLM call for complete task analysis.
        Uses existing tool_capabilities infrastructure for zero hardcoding.
        
        Args:
            task: Task to analyze
            
        Returns:
            Complete analysis dict or None if LLM fails
        """
        if not self.llm_service:
            return None
        
        # Use existing infrastructure - load tools from registry
        from src.routing.tool_capabilities import get_tool_registry
        
        tool_registry = get_tool_registry()
        if not tool_registry:
            return None
        
        # Build compact tool list with parameter formats and examples
        tools_str = ""
        for name, info in tool_registry.items():
            if name.startswith("$"):  # Skip metadata
                continue
            
            desc = info.get('description', '')
            param_format = info.get('parameter_format', {})
            example_usage = info.get('example_usage', {})
            usage_note = info.get('usage_note', '')
            
            tools_str += f"- {name}: {desc}\n"
            
            # Add usage note if available (for playwright_execute)
            if usage_note:
                tools_str += f"  Note: {usage_note}\n"
            
            # Add parameter format if available
            if param_format:
                tools_str += "  Params: "
                params = []
                for param_name, param_desc in param_format.items():
                    params.append(f"{param_name}={param_desc}")
                tools_str += "; ".join(params) + "\n"
            
            # Add example usage if available (for playwright_execute)
            if example_usage:
                tools_str += "  Examples:\n"
                for example_name, example_obj in list(example_usage.items())[:2]:  # Show max 2 examples
                    tools_str += f"    {example_name}: {json.dumps(example_obj)}\n"
        
        # Build comprehensive analysis prompt (compact, schema-driven)
        prompt = f"""Analyze task and return JSON.

Task: "{task.description}"

Available Tools:
{tools_str}

**CRITICAL: Sequential Task Parameter Rules**

For multi-step tasks, the system AUTOMATICALLY passes data between steps:
- Step 1 outputs (URLs, data, etc.) are AUTOMATICALLY available to Step 2
- You MUST NOT include parameters in Step 2 that come from Step 1
- The DataFlowResolver handles ALL data passing automatically

**WRONG Examples (DO NOT DO THIS):**

❌ Example 1 - Using placeholder variable:
{{
  "steps": [
    {{"tool": "google_search", "parameters": {{"query": "TechCrunch AI"}}}},
    {{"tool": "chart_extractor", "parameters": {{"url": "{{techcrunch}}"}}}}
  ]
}}

❌ Example 2 - Using PREVIOUS_STEP_RESULT:
{{
  "steps": [
    {{"tool": "google_search", "parameters": {{"query": "AI news"}}}},
    {{"tool": "chart_extractor", "parameters": {{"url": "PREVIOUS_STEP_RESULT.url"}}}}
  ]
}}

❌ Example 3 - Using variable.field syntax:
{{
  "steps": [
    {{"tool": "google_search", "parameters": {{"query": "news"}}}},
    {{"tool": "chart_extractor", "parameters": {{"url": "{{search.urls[0]}}"}}}}
  ]
}}

**CORRECT Example (DO THIS):**

✅ Omit the url parameter completely - system will auto-add it:
{{
  "steps": [
    {{"tool": "google_search", "parameters": {{"query": "TechCrunch AI articles"}}}},
    {{"tool": "chart_extractor", "parameters": {{"required_fields": ["headline", "author"], "limit": 5}}}}
  ]
}}

**Why this works:**
1. google_search returns URLs in its output
2. DataFlowResolver extracts URLs from search results
3. chart_extractor's schema says it "accepts_from": ["google_search.urls[0]"]
4. Resolver AUTOMATICALLY adds url parameter from google_search output
5. chart_extractor receives the actual URL without you specifying it

**Rule:** If a parameter will come from a previous step, DO NOT include it in the JSON. The system handles it.

Return JSON:
{{
    "task_type": "search|api_request|web_scraping|general",
    "query_params": {{}},
    "required_tools": ["tool1"],
    "required_fields": ["field1"],
    "task_structure": {{
        "type": "single|sequential",
        "steps": [{{"tool": "tool1", "parameters": {{}}}}]
    }}
}}

RETURN ONLY VALID JSON:"""
        
        try:
            print("[REASON] 🎯 Comprehensive analysis (1 LLM call)")
            
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content.strip()
            
            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                print(f"[REASON] ✓ Found JSON match (length: {len(json_match.group())} chars)")
                analysis = json.loads(json_match.group())
                
                # DEBUG LOGGING
                print(f"[REASON] 🔍 DEBUG: Full analysis from LLM:")
                print(f"[REASON] 🔍   - task_type: {analysis.get('task_type')}")
                print(f"[REASON] 🔍   - required_tools: {analysis.get('required_tools')}")
                print(f"[REASON] 🔍   - task_structure: {analysis.get('task_structure')}")
                print(f"[REASON] 🔍   - task_structure.type: {analysis.get('task_structure', {}).get('type')}")
                print(f"[REASON] 🔍   - task_structure.steps: {analysis.get('task_structure', {}).get('steps')}")
                
                print(f"[REASON] ✓ Analysis complete: type={analysis.get('task_type')}, tools={len(analysis.get('required_tools', []))}, structure={analysis.get('task_structure', {}).get('type')}")
                return analysis
            else:
                print("[REASON] ✗ Could not parse LLM response")
                return None
                
        except Exception as e:
            print(f"[REASON] ✗ Comprehensive analysis failed: {e}")
            return None
    
    def _extract_query_params(self, description: str) -> Dict[str, Any]:
        """
        Use LLM to extract query parameters from description.
        
        Example: "Get latest 10 posts" → {"limit": 10, "sort": "id", "order": "desc"}
        
        Args:
            description: Task description
            
        Returns:
            Dictionary of query parameters
        """
        if not self.llm_service:
            return {}
        
        prompt = f"""Extract API query parameters from this request.

Request: "{description}"

Common patterns:
- "latest N" → {{"limit": N, "sort": "id", "order": "desc"}}
- "top N" → {{"limit": N, "sort": "rank", "order": "asc"}}
- "first N" → {{"limit": N}}

Return ONLY a JSON object with parameters, or {{}} if none needed.

JSON:"""
        
        try:
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content.strip()
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[REASON] Query param extraction failed: {e}")
        
        return {}
    
    def _detect_task_type(self, description: str) -> str:
        """
        Detect task type by matching against tool capabilities from registry.
        Uses LLM to understand which tools would be appropriate.
        NO HARDCODING - adapts to available tools.
        
        Args:
            description: Task description
            
        Returns:
            Task type string
        """
        # Get tool descriptions from registry
        tool_descriptions = self._get_tool_descriptions()
        
        if not tool_descriptions or not self.llm_service:
            return "general"
        
        # Build prompt with tool capabilities
        prompt = f"""Analyze this task and determine its type based on available tool capabilities.

Task: "{description}"

Available Tools:
"""
        for tool_name, tool_desc in tool_descriptions.items():
            prompt += f"- {tool_name}: {tool_desc}\n"
        
        prompt += """
Based on the tools available, what type of task is this?

Types:
- text_generation: No tools needed, pure text generation (emails, writing, etc.)
- api_request: Needs API calls or HTTP requests
- web_scraping: Needs browser automation or web scraping
- search: Needs web search
- general: Other tasks

Return ONLY the type name (one word).

Type:"""
        
        try:
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            task_type = response.content.strip().lower()
            
            # Validate response
            valid_types = ["text_generation", "api_request", "web_scraping", "search", "general"]
            if task_type in valid_types:
                print(f"[REASON] Detected task type: {task_type}")
                return task_type
            else:
                print(f"[REASON] Invalid task type '{task_type}', defaulting to general")
                return "general"
        except Exception as e:
            print(f"[REASON] Task type detection failed: {e}")
            return "general"
    
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
                    # Try multiple ways to get tool info
                    if hasattr(tool, 'name') and hasattr(tool, 'description'):
                        descriptions[tool.name] = tool.description
                    elif hasattr(tool, 'func'):
                        # LangChain tool wrapper
                        func = tool.func if callable(tool.func) else tool
                        if hasattr(func, 'name'):
                            name = func.name # pyright: ignore[reportFunctionMemberAccess]
                            desc = getattr(func, 'description', f"Tool: {name}")
                            descriptions[name] = desc
        
        # If still empty, load from tool registry file
        if not descriptions:
            try:
                import json
                from pathlib import Path
                registry_path = Path(__file__).parent.parent.parent / "tool_registry.json"
                if registry_path.exists():
                    with open(registry_path, 'r') as f:
                        registry = json.load(f)
                        # Handle flat dictionary format
                        for tool_name, tool_data in registry.items():
                            if not tool_name.startswith("_"):  # Skip disabled tools
                                # Use tool_name (registry key) as description key, not tool value
                                # This prevents playwright_click, playwright_fill, etc from overwriting each other
                                desc = tool_data.get("description", f"Tool: {tool_name}")
                                descriptions[tool_name] = desc
                    print(f"[REASON] Loaded {len(descriptions)} tool descriptions from registry file")
            except Exception as e:
                print(f"[REASON] Failed to load from registry file: {e}")
                import traceback
                traceback.print_exc()
        
        self._tool_descriptions = descriptions
        print(f"[REASON] Loaded {len(descriptions)} tool descriptions")
        return descriptions
    
    def _llm_tool_selection(self, task: AgentTask) -> List[str]:
        """
        Use LLM to intelligently select tools based on descriptions.
        Enhanced with few-shot examples and better prompting.
        Uses the reason agent prompt for better guidance.
        
        Args:
            task: Task to analyze
            
        Returns:
            List of selected tool names
        """
        tool_descriptions = self._get_tool_descriptions()
        
        if not tool_descriptions:
            print("[REASON] No tool descriptions available, using keyword fallback")
            return []
        
        # Get reason agent guidance
        reason_prompt = get_reason_agent_prompt(self.available_tools)
        
        # Build prompt with few-shot examples and reason agent context
        prompt = f"""You are an expert task planner. Select the right tools to accomplish user requests.

IMPORTANT FROM YOUR INSTRUCTIONS:
- You can use the SAME tool MULTIPLE times with different parameters
- Don't stop after one search if results are incomplete
- For "find top 10 X", you may need multiple searches to get all 10
- Check conversation history for previous context

Available Tools:
"""
        # Show only most relevant tools to reduce token usage
        relevant_tools = {
            "google_search": "Search Google for information",
            "playwright_execute": "Automate browser actions (navigate, click, fill forms, extract data)",
            "chart_extractor": "Extract structured data (tables, lists) from webpages"
        }
        
        for name, desc in relevant_tools.items():
            prompt += f"- {name}: {desc}\n"
        
        prompt += f"""
FEW-SHOT EXAMPLES:

Example 1:
User: "Find weather in Paris"
Tools: ["google_search"]
Reasoning: Simple search query, no extraction needed

Example 2:
User: "Find top 10 restaurants in NYC with phone numbers"
Tools: ["google_search", "playwright_execute"]
Reasoning: Search first, then use playwright to visit pages and extract structured data

Example 3:
User: "Go to example.com and fill the contact form"
Tools: ["playwright_execute"]
Reasoning: Direct browser automation, no search needed

Example 4:
User: "What are the best laptops under $1000"
Tools: ["google_search"]
Reasoning: Information query, search is sufficient

YOUR TURN:
User Request: "{task.description}"

Think step-by-step:
1. Does this need web search? (finding information, discovering sources)
2. Does this need browser automation? (visiting sites, clicking, filling forms)
3. Does this need structured extraction? (tables, lists, multiple items with fields)

Return ONLY a JSON array of tool names:
["tool1", "tool2"]

Important:
- For "find X restaurants/hotels/places with details" → use ["google_search", "playwright_execute"]
- For "go to X.com and do Y" → use ["playwright_execute"]
- For "what is/find information about X" → use ["google_search"]
- If query asks for phone numbers, addresses, websites → include playwright_execute for extraction

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
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                tools_json = json_match.group()
                tools = json.loads(tools_json)
                
                # Validate tools exist
                valid_tools = [t for t in tools if t in relevant_tools]
                
                if valid_tools:
                    print(f"[REASON] LLM selected tools: {valid_tools}")
                    return valid_tools
                else:
                    print(f"[REASON] LLM selected invalid tools: {tools}, using fallback")
                    return []
            else:
                print("[REASON] Could not parse LLM response, using fallback")
                return []
                
        except Exception as e:
            print(f"[REASON] LLM tool selection failed: {e}")
            return []
    
    def _identify_required_tools(self, task: AgentTask) -> List[str]:
        """
        Identify which tools are needed using LLM-based selection with keyword fallback.
        Simple, intelligent, and works for any query type.
        
        Args:
            task: Task to analyze
            
        Returns:
            List of required tool names in execution order
        """
        # Check if this is a follow-up question
        if self._is_followup_question(task.description):
            print("[REASON] Detected follow-up question - using previous context")
            return []  # No tools needed, will use previous results
        
        print("[REASON] Using LLM-based tool selection...")
        tools = self._llm_tool_selection(task)
        
        # If LLM selection fails, use keyword-based fallback
        if not tools:
            print("[REASON] LLM selection failed, using keyword fallback")
            tools = self._keyword_based_tool_selection(task)
        
        return tools
    
    def _is_followup_question(self, query: str) -> bool:
        """
        Use LLM to detect if query is a follow-up to previous conversation.
        ZERO HARDCODING - works for ANY follow-up pattern.
        
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
            print(f"[REASON] DEBUG: Got last_query from previous_results: '{last_query}'")
        
        # Fallback: use conversation_history if previous_results is empty/broken
        if not last_query and len(self.conversation_history) >= 2:
            print("[REASON] DEBUG: previous_results empty, trying conversation_history")
            # Get last user message (skip current one which hasn't been added yet)
            for msg in reversed(self.conversation_history):
                if msg["role"] == "user":
                    last_query = msg["content"]
                    print(f"[REASON] DEBUG: Got last_query from conversation_history: '{last_query}'")
                    break
        
        # If still no last_query, can't be follow-up
        if not last_query:
            print("[REASON] No previous query found - cannot be follow-up")
            return False
        
        # Don't waste LLM call if queries are identical
        if query.lower().strip() == last_query.lower().strip():
            print("[REASON] Queries are identical - not a follow-up")
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
                print("[REASON] No LLM service, cannot detect follow-up")
                return False
            
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            answer = response.content.strip().lower()
            
            is_followup = "yes" in answer
            print(f"[REASON] Follow-up detection: {is_followup} ('{query}' vs '{last_query}')")
            return is_followup
            
        except Exception as e:
            print(f"[REASON] Follow-up detection failed: {e}")
            # Fallback: check for very obvious patterns
            query_lower = query.lower().strip()
            return any(word in query_lower for word in ["table", "format", "show", "display"]) and len(query.split()) < 10
    
    def _keyword_based_tool_selection(self, task: AgentTask) -> List[str]:
        """
        Fallback tool selection using tool categories from schema.
        ZERO HARDCODING - uses tool metadata from schema.
        
        Args:
            task: Task to analyze
            
        Returns:
            List of tool names based on schema categories
        """
        resolver = get_resolver()
        description = task.description.lower()
        
        # Get all tools grouped by category from schema
        schema_stats = resolver.get_schema_stats()
        tools_by_category = schema_stats.get("tools_by_category", {})
        
        # Score each category based on task description
        category_scores = {}
        
        for category, tool_list in tools_by_category.items():
            score = 0
            
            # Score based on category keywords
            if category == "browser_automation":
                keywords = ["navigate", "visit", "click", "fill", "goto", "browser", "open"]
                score = sum(1 for kw in keywords if kw in description)
            
            elif category == "search":
                keywords = ["search", "find", "look up", "google", "query"]
                score = sum(1 for kw in keywords if kw in description)
            
            elif category == "extraction":
                keywords = ["extract", "scrape", "get data", "table", "list"]
                score = sum(1 for kw in keywords if kw in description)
            
            elif category == "api":
                keywords = ["api", "endpoint", "http", "request"]
                score = sum(1 for kw in keywords if kw in description)
            
            if score > 0:
                category_scores[category] = score
        
        # Select tools from highest scoring category
        if category_scores:
            best_category = max(category_scores, key=lambda cat: category_scores[cat])
            tools = tools_by_category.get(best_category, [])
            if tools:
                print(f"[REASON] Fallback: Selected {tools} from category '{best_category}'")
                return tools
        
        # Ultimate fallback: return first search tool
        search_tools = tools_by_category.get("search", [])
        if search_tools:
            print(f"[REASON] Fallback: Defaulting to search tool: {search_tools[0]}")
            return [search_tools[0]]
        
        # If all else fails, return google_search
        print("[REASON] Fallback: Defaulting to google_search")
        return ["google_search"]
    
    def _needs_structured_extraction(self, query: str) -> bool:
        """
        Use LLM to determine if query needs structured data extraction.
        Zero hardcoding - works for ANY query type.
        """
        prompt = f"""Does this query require extracting structured data from webpages?

Query: "{query}"

Structured extraction means:
- Lists (top 10, best 5, rankings)
- Tables (comparisons, stats, data)
- Collections (items with multiple fields)

Non-structured:
- Simple facts ("what is...")
- Definitions
- Single answers

Answer: yes or no

Answer:"""
        
        try:
            if not self.llm_service:
                # Fallback: check for numbers
                import re
                return bool(re.search(r'\d+|top|best|list', query.lower()))
            
            response = self.llm_service.get_model().invoke(prompt)
            answer = response.content.strip().lower()
            needs_extraction = "yes" in answer
            print(f"[REASON] Structured extraction needed: {needs_extraction}")
            return needs_extraction
        except:
            # Fallback: assume yes if query has numbers or keywords
            import re
            return bool(re.search(r'\d+|top|best|list', query.lower()))
    
    def _extract_required_fields_llm(self, query: str) -> List[str]:
        """
        Use LLM to extract user-requested fields AND suggest additional useful fields.
        Zero hardcoding - works for any query type.
        """
        prompt = f"""Analyze this query and extract field requirements.

Query: "{query}"

Return JSON with:
1. Fields user explicitly requested
2. Additional fields that would be useful (specs, details, etc.)
3. Category/type of data
4. Time period (year, date range)

Example for "top 10 laptops of 2024":
{{
    "user_requested": ["name", "rank"],
    "suggested": ["CPU", "RAM", "storage", "GPU", "price", "rating", "release_date"],
    "category": "laptops",
    "year": 2024
}}

Example for "best restaurants in NYC with phone":
{{
    "user_requested": ["name", "phone"],
    "suggested": ["address", "cuisine", "price_range", "rating", "hours"],
    "category": "restaurants",
    "location": "NYC"
}}

Return ONLY valid JSON:"""
        
        try:
            if not self.llm_service:
                # Fallback
                return ["name", "description"]
            
            response = self.llm_service.get_model().invoke(prompt)
            content = response.content.strip()
            
            # Parse JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Combine user requested + suggested
                user_fields = result.get("user_requested", [])
                suggested_fields = result.get("suggested", [])
                all_fields = user_fields + suggested_fields
                
                # Remove duplicates while preserving order
                seen = set()
                final_fields = []
                for field in all_fields:
                    if field not in seen:
                        seen.add(field)
                        final_fields.append(field)
                
                print(f"[REASON] User requested: {user_fields}")
                print(f"[REASON] Suggested: {suggested_fields}")
                print(f"[REASON] Final fields: {final_fields}")
                
                # Store metadata
                if "category" in result:
                    print(f"[REASON] Category: {result['category']}")
                if "year" in result:
                    print(f"[REASON] Year: {result['year']}")
                
                return final_fields
        except Exception as e:
            print(f"[REASON] Field extraction failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback
        return ["name", "description"]
    
    def _extract_urls_from_search(self, search_results: str) -> List[str]:
        """
        Extract URLs from search results.
        Returns top relevant URLs for extraction.
        """
        import re
        
        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, search_results)
        
        # Filter out common non-content URLs
        filtered_urls = [
            url for url in urls[:10]  # Top 10 results
            if not any(skip in url.lower() for skip in [
                'google.com', 'youtube.com/results', 'facebook.com',
                'twitter.com', 'linkedin.com', 'instagram.com'
            ])
        ]
        
        print(f"[REASON] Extracted {len(filtered_urls)} URLs from search")
        return filtered_urls[:3]  # Top 3 URLs
    
    def _create_extraction_tasks_from_urls(
        self,
        urls: List[str],
        required_fields: List[str],
        base_task_id: str
    ) -> List[Dict[str, Any]]:
        """
        Create extraction tasks for each URL.
        Uses playwright_execute to navigate, then chart_extractor to extract.
        This leverages the persistent browser from UniversalPlaywrightTool.
        """
        tasks = []
        
        for i, url in enumerate(urls):
            # Task 1: Navigate to URL using persistent browser
            tasks.append({
                "subtask_id": f"{base_task_id}_nav_{i}",
                "tool": "playwright_execute",
                "parameters": {
                    "url": url,
                    "method": "goto"
                },
                "description": f"Navigate to {url}"
            })
            
            # Task 2: Extract data from current page
            tasks.append({
                "subtask_id": f"{base_task_id}_extract_{i}",
                "tool": "chart_extractor",
                "parameters": {
                    "required_fields": required_fields
                },
                "description": f"Extract structured data from current page"
            })
        
        print(f"[REASON] Created {len(tasks)} extraction tasks (navigate + extract pairs)")
        return tasks
    
    def _create_plan(self, task: AgentTask, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create execution plan based on analysis.
        Uses pre-analyzed data to avoid additional LLM calls.
        
        Args:
            task: Task to plan for
            analysis: Task analysis (already contains fields, structure, etc.)
            
        Returns:
            Execution plan
        """
        required_tools = analysis.get("required_tools", [])
        complexity = analysis.get("complexity", "simple")
        task_structure = analysis.get("task_structure", {"type": "single"})
        
        plan = {
            "needs_delegation": len(required_tools) > 0,
            "complexity": complexity,
            "subtasks": [],
            "needs_follow_up_extraction": False,
            "required_fields": [],
            "original_task_id": task.task_id,
            "task_structure": task_structure,  # Pass structure to decomposer
            "has_explicit_extraction": any(
                tool in ["chart_extractor", "playwright_execute", "extract_data", "extract_structured"]
                for tool in required_tools
            )
        }
        
        # Use pre-analyzed required fields (no additional LLM call)
        required_fields = analysis.get("required_fields", [])
        if required_fields:
            print(f"[REASON] Using pre-analyzed fields: {required_fields}")
            plan["needs_follow_up_extraction"] = True
            plan["required_fields"] = required_fields
        
        # Use decomposer if we have pre-analyzed steps (type-agnostic)
        if task_structure.get("steps"):
            num_steps = len(task_structure.get("steps", []))
            structure_type = task_structure.get("type", "unknown")
            print(f"[REASON] Found {num_steps} pre-analyzed steps (type: {structure_type}), using decomposer")
            
            # Pass comprehensive context to decomposer
            decomposer_context = {
                "query_params": analysis.get("query_params", {}),
                "task_type": analysis.get("detected_type", "general"),
                "task_structure": task_structure,
                "required_fields": required_fields
            }
            
            decomposed_subtasks = self.task_decomposer.decompose(
                task.description, 
                task.task_id, 
                decomposer_context
            )
            
            if decomposed_subtasks:
                print(f"[REASON] ✓ Decomposer created {len(decomposed_subtasks)} subtasks")
                plan["subtasks"] = decomposed_subtasks
                
                # Log the plan
                print(f"\n{'='*60}")
                print(f"📋 EXECUTION PLAN ({len(plan['subtasks'])} steps)")
                for idx, subtask in enumerate(plan['subtasks'], 1):
                    print(f"  {idx}. {subtask['tool']}: {subtask.get('parameters', {})}")
                print(f"{'='*60}\n")
                
                return plan
            else:
                print("[REASON] ⚠️ Decomposer returned nothing, using fallback logic")
        
        # FALLBACK: Use existing logic for playwright-specific or other cases
        if "playwright_execute" in required_tools:
            print("[REASON] Using LLM-based task decomposer for playwright")
            # Pass comprehensive context including task structure
            decomposer_context = {
                "query_params": analysis.get("query_params", {}),
                "task_type": analysis.get("detected_type", "general"),
                "task_structure": task_structure,  # Pass pre-analyzed structure
                "required_fields": required_fields  # Pass pre-analyzed fields
            }
            decomposed_subtasks = self.task_decomposer.decompose(task.description, task.task_id, decomposer_context)
            
            if decomposed_subtasks:
                plan["subtasks"] = decomposed_subtasks
            else:
                # Fallback to old method if decomposer fails
                print("[REASON] Decomposer failed, using fallback")
                for i, tool in enumerate(required_tools):
                    if tool == "playwright_execute":
                        playwright_subtasks = self._parse_playwright_task(task.description, task.task_id, i)
                        plan["subtasks"].extend(playwright_subtasks)
                    else:
                        tool_params = self._map_parameters_for_tool(tool, task.parameters, task.description)
                        subtask = {
                            "subtask_id": f"{task.task_id}_sub_{i}",
                            "tool": tool,
                            "parameters": tool_params,
                            "description": f"Use {tool} for: {task.description}"
                        }
                        plan["subtasks"].append(subtask)
        else:
            # For non-playwright tools, use existing logic
            for i, tool in enumerate(required_tools):
                tool_params = self._map_parameters_for_tool(tool, task.parameters, task.description)
                subtask = {
                    "subtask_id": f"{task.task_id}_sub_{i}",
                    "tool": tool,
                    "parameters": tool_params,
                    "description": f"Use {tool} for: {task.description}"
                }
                plan["subtasks"].append(subtask)
        
        # Log the plan
        print(f"\n{'='*60}")
        print(f"📋 EXECUTION PLAN ({len(plan['subtasks'])} steps)")
        for idx, subtask in enumerate(plan['subtasks'], 1):
            print(f"  {idx}. {subtask['tool']}: {subtask.get('parameters', {})}")
        print(f"{'='*60}\n")
        
        return plan
    
    def _parse_playwright_task(
        self,
        description: str,
        task_id: str,
        base_index: int
    ) -> List[Dict[str, Any]]:
        """
        Parse a complex Playwright task description into multiple subtasks.
        
        Args:
            description: Task description
            task_id: Base task ID
            base_index: Starting index for subtask IDs
            
        Returns:
            List of subtask dictionaries
        """
        import re
        
        subtasks = []
        subtask_counter = 0
        
        # Extract URL
        url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
        url_match = re.search(url_pattern, description)
        url = None
        if url_match:
            url = url_match.group(0).rstrip(',.;:!?')
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
        
        # Step 1: Navigation (if URL found)
        if url:
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "url": url,
                    "method": "goto",
                    "args": {}
                },
                "description": f"Navigate to {url}"
            })
            subtask_counter += 1
        
        # Step 2: Look for search actions (e.g., "search for X", "search X")
        search_pattern = r'(?:search|find|look\s+for|query)\s+(?:for\s+)?["\']?([^"\']+?)["\']?(?:\s+(?:on|in|at)|$)'
        search_match = re.search(search_pattern, description, re.IGNORECASE)
        
        if search_match:
            search_query = search_match.group(1).strip()
            # Remove trailing "and" or other connectors
            search_query = re.sub(r'\s+(?:and|then|,).*$', '', search_query, flags=re.IGNORECASE)
            
            # Add search box fill
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "method": "fill",
                    "selector": "input[name='search'], input[type='search'], input[placeholder*='search' i], input[aria-label*='search' i]",
                    "args": {"value": search_query}
                },
                "description": f"Enter search query: {search_query}"
            })
            subtask_counter += 1
            
            # Add press Enter or click search button
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "method": "press",
                    "selector": "input[name='search'], input[type='search']",
                    "args": {"key": "Enter"}
                },
                "description": "Submit search"
            })
            subtask_counter += 1
        
        # Step 3: Look for fill/type actions (existing logic)
        # Use a single comprehensive pattern that handles "and" properly
        # Matches: "X as 'Y'" or "fill X as 'Y'" etc, stopping before "and" or ","
        fill_pattern = r'(?:fill\s+in\s+(?:the\s+)?|fill\s+(?:the\s+)?)?([^,]+?)\s+as\s+["\']([^"\']+)["\']'
        
        matches = re.finditer(fill_pattern, description, re.IGNORECASE)
        for match in matches:
            field = match.group(1).strip()
            value = match.group(2).strip()
            
            # Skip if field contains "go to" or other navigation terms
            if any(term in field.lower() for term in ['go to', 'navigate', 'visit', 'then', 'submit', 'search']):
                continue
            
            # Try to map field name to selector
            selector = self._field_to_selector(field)
            
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "method": "fill",
                    "selector": selector,
                    "args": {"value": value}
                },
                "description": f"Fill {field} with {value}"
            })
            subtask_counter += 1
        
        # Step 4: Look for click/submit actions
        if re.search(r'\bsubmit\b', description, re.IGNORECASE):
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "method": "click",
                    "selector": "input[type='submit'], button[type='submit']",
                    "args": {}
                },
                "description": "Submit the form"
            })
            subtask_counter += 1
        
        # If no specific actions found, just do navigation
        if not subtasks:
            subtasks.append({
                "subtask_id": f"{task_id}_pw_{base_index}_{subtask_counter}",
                "tool": "playwright_execute",
                "parameters": {
                    "url": url,
                    "method": "goto",
                    "args": {}
                },
                "description": f"Navigate to {url}"
            })
        
        return subtasks
    
    def _field_to_selector(self, field_name: str) -> str:
        """
        Convert a field name to a likely CSS selector.
        
        Args:
            field_name: Human-readable field name
            
        Returns:
            CSS selector string
        """
        field_lower = field_name.lower()
        
        # Common field name mappings
        field_mappings = {
            "customer name": "input[name='custname'], input[name='customer_name'], input[id='custname']",
            "comment": "textarea[name='comments'], textarea[name='comment'], textarea[id='comments']",
            "email": "input[type='email'], input[name='email']",
            "password": "input[type='password'], input[name='password']",
            "username": "input[name='username'], input[name='user']",
            "phone": "input[type='tel'], input[name='phone']",
            "name": "input[name='name'], input[name='custname']"
        }
        
        # Check for exact match first
        for key, selector in field_mappings.items():
            if key in field_lower:
                return selector
        
        # Default: try to create a selector from the field name
        # Remove spaces and special chars for name attribute
        cleaned = field_lower.replace(" ", "_").replace("'", "").replace('"', '')
        return f"input[name='{cleaned}'], textarea[name='{cleaned}'], input[id='{cleaned}']"
    
    def _map_parameters_for_tool(
        self,
        tool_name: str,
        base_params: Dict[str, Any],
        description: str
    ) -> Dict[str, Any]:
        """
        Map parameters using tool schema.
        ZERO HARDCODING - uses tool_io_schema.json.
        
        Args:
            tool_name: Name of the tool
            base_params: Base parameters from task
            description: Task description
            
        Returns:
            Properly mapped parameters for the tool
        """
        resolver = get_resolver()
        
        # Get tool's input schema
        tool_inputs = resolver.get_tool_inputs(tool_name)
        
        if not tool_inputs:
            # No schema, use simple fallback
            query = base_params.get("query", description)
            return {"query": query}
        
        params = {}
        query = base_params.get("query", description)
        
        # For each input in schema, try to provide a value
        for input_name, input_spec in tool_inputs.items():
            # Add defaults for non-required inputs
            if not input_spec.get("required", False):
                if "default" in input_spec:
                    params[input_name] = input_spec["default"]
                continue
            
            # Map based on input name (schema-driven)
            if input_name == "query":
                params["query"] = query
            elif input_name == "expression":
                params["expression"] = query
            elif input_name == "url":
                # Extract URL from description
                url = self._extract_url_from_description(description)
                if url:
                    params["url"] = url
            elif input_name == "method":
                params["method"] = "goto"
            elif input_name == "args":
                params["args"] = {}
            elif input_name == "content":
                params["content"] = ""  # Will be filled by resolver
            elif input_name == "data_type":
                params["data_type"] = "html"
        
        # If no params were set, provide minimal fallback
        if not params:
            params = {"query": query}
        
        return params
    
    def _extract_url_from_description(self, description: str) -> Optional[str]:
        """
        Extract URL from description (schema-agnostic helper).
        
        Args:
            description: Task description
            
        Returns:
            Extracted URL or None
        """
        import re
        url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
        match = re.search(url_pattern, description)
        
        if match:
            url = match.group(0).rstrip(',.;:!?')
            # Ensure protocol
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            return url
        
        return None
    
    async def _execute_parallel_extraction(
        self,
        urls: List[str],
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract from multiple URLs in PARALLEL using separate browser contexts.
        Each URL gets its own tab/context.
        
        Args:
            urls: List of URLs to extract from
            required_fields: Fields to extract
            
        Returns:
            List of extraction results
        """
        print(f"[REASON] 🚀 Starting PARALLEL extraction from {len(urls)} URLs")
        
        try:
            from playwright.async_api import async_playwright
            import os
            
            # Respect HEADLESS environment variable (same as main playwright tool)
            headless_mode = os.getenv("HEADLESS", "true").lower() == "true"
            print(f"[REASON] Browser mode: {'headless' if headless_mode else 'headed'}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless_mode)
                
                # Create extraction tasks for each URL (parallel)
                tasks = [
                    self._extract_single_url(browser, url, required_fields)
                    for url in urls
                ]
                
                # Run ALL URLs in parallel with 3-minute overall timeout
                try:
                    async with asyncio.timeout(180):  # 3 minutes for all
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                except asyncio.TimeoutError:
                    print(f"[REASON] ⚠️ Overall timeout - using partial results")
                    results = []
                
                await browser.close()
                
                # Filter successful results (only dicts, not exceptions)
                successful: List[Dict[str, Any]] = []
                for r in results:
                    if not isinstance(r, Exception) and isinstance(r, dict) and r.get('success'):
                        successful.append(r)
                
                print(f"[REASON] ✅ Parallel extraction complete: {len(successful)}/{len(urls)} URLs")
                return successful
                
        except Exception as e:
            print(f"[REASON] ❌ Parallel extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _extract_single_url(
        self,
        browser: Any,
        url: str,
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Extract from one URL in a separate context (tab).
        Uses parallel element extraction internally.
        NOW WITH SITE INTELLIGENCE!
        
        Args:
            browser: Playwright browser instance
            url: URL to extract from
            required_fields: Fields to extract
            
        Returns:
            Extraction result dict
        """
        try:
            async with asyncio.timeout(120):  # 2 minutes per URL
                # Create new context (like a new tab)
                context = await browser.new_context()
                page = await context.new_page()
                
                print(f"[REASON] 📄 Extracting from {url}")
                
                # Navigate
                await page.goto(url, wait_until='domcontentloaded')
                
                # DISABLED: Site Intelligence (causing JSON parsing issues)
                # TODO: Re-enable after fixing "Extra data" JSON parsing
                # from urllib.parse import urlparse
                # domain = urlparse(url).netloc
                # ... (Site Intelligence code commented out)
                print(f"[REASON] ⚠️ Site Intelligence disabled - extracting directly")
                
                # Get HTML
                html = await page.content()
                
                # Extract with PARALLEL element extraction
                from src.tools.universal_extractor import UniversalExtractor, SmartSearcher
                
                extractor = UniversalExtractor()
                all_data = await extractor.extract_everything_async(html, url)
                
                # Search for required fields
                searcher = SmartSearcher()
                query = ' '.join(required_fields)
                records = searcher.search(all_data, query, required_fields)
                
                # NEW: Validate with SchemaBuilder
                if records:
                    try:
                        from src.utils.schema_builder import SchemaBuilder
                        
                        builder = SchemaBuilder()
                        
                        # Build schema from first few records
                        schema = builder.build_schema(records[:5])
                        print(f"[REASON] 📋 Built schema with {len(schema.get('fields', {}))} fields")
                        
                        # Validate each record
                        complete_count = 0
                        incomplete_count = 0
                        
                        for record in records:
                            validation = builder.validate_record(record, schema)
                            if validation['valid'] and validation['completeness'] > 0.7:
                                complete_count += 1
                            else:
                                incomplete_count += 1
                        
                        print(f"[REASON] ✓ Validated: {complete_count} complete, {incomplete_count} incomplete")
                        
                    except Exception as e:
                        print(f"[REASON] ⚠️ Schema validation failed: {e}")
                
                await context.close()
                
                print(f"[REASON] ✅ Extracted {len(records)} records from {url}")
                
                return {
                    'url': url,
                    'data': records,
                    'success': True,
                    'count': len(records)
                }
                
        except asyncio.TimeoutError:
            print(f"[REASON] ⏱️ Timeout extracting from {url}")
            return {
                'url': url,
                'success': False,
                'error': 'timeout'
            }
        except Exception as e:
            print(f"[REASON] ❌ Error extracting from {url}: {e}")
            return {
                'url': url,
                'success': False,
                'error': str(e)
            }
    
    def _execute_delegation(self, subtasks: List[Dict[str, Any]], plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Delegate tasks to executor agents with AUTOMATIC data flow resolution.
        Uses DataFlowResolver for zero-hardcoding parameter chaining.
        
        Args:
            subtasks: List of subtasks to delegate
            plan: Optional execution plan with extraction settings
            
        Returns:
            List of results from executors
        """
        # Initialize DataFlowResolver for automatic data flow
        resolver = get_resolver()
        print("[REASON] 🔄 Using DataFlowResolver for automatic parameter resolution")
        
        results = []
        accumulated_data = {}  # Track all tool outputs with structure
        
        # Track follow-ups per tool to prevent infinite loops
        MAX_FOLLOW_UPS_PER_TOOL = 5
        follow_up_counts = {}
        previous_coverage = {}
        extraction_tasks_added = False
        
        for i, subtask in enumerate(subtasks):
            tool_name = subtask["tool"]
            provided_params = subtask["parameters"]
            
            print(f"[REASON] === Subtask {i+1}/{len(subtasks)}: {tool_name} ===")
            
            # AUTOMATIC INPUT RESOLUTION (replaces _chain_parameters)
            resolved_params = resolver.resolve_inputs(
                tool_name=tool_name,
                provided_params=provided_params,
                accumulated_data=accumulated_data
            )
            
            # Update subtask with resolved parameters
            subtask["parameters"] = resolved_params
            
            # Find executor agent that can handle this tool
            executor = self._find_executor_for_tool(subtask["tool"])
            
            if not executor:
                print(f"[REASON] ERROR: No executor found for tool: {subtask['tool']}")
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
                print(f"[REASON] ✓ Subtask {i+1}/{len(subtasks)}: {tool_name} - {result.success}")
                
                # AUTOMATIC OUTPUT EXTRACTION (zero hardcoding)
                extracted_outputs = resolver.extract_outputs(
                    tool_name=tool_name,
                    raw_result=result.data
                )
                
                # Store in accumulated data with structure preservation
                step_name = f"step_{i}_{tool_name}"
                accumulated_data[step_name] = {
                    "tool": tool_name,
                    "result": result,
                    "extracted": extracted_outputs,
                    "timestamp": datetime.now().isoformat()
                }
                
                print(f"[REASON] 📦 Accumulated data: {list(extracted_outputs.keys())}")
                
                result_entry = {
                    "subtask_id": subtask["subtask_id"],
                    "tool": tool_name,
                    "success": result.success,
                    "data": result.data,
                    "metadata": result.metadata
                }
                results.append(result_entry)
                
                self.log(f"Subtask completed: {tool_name} - Success: {result.success}")
                
                # NEW: Auto-extraction after search completes WITH PARALLEL EXECUTION!
                # Only run if NO explicit extraction tool in plan
                if (result.success and 
                    subtask["tool"] == "google_search" and 
                    plan and 
                    plan.get("needs_follow_up_extraction") and 
                    not extraction_tasks_added and
                    not plan.get("has_explicit_extraction", False)):
                    
                    print("[REASON] ✨ Auto-creating PARALLEL extraction from search results")
                    
                    # Extract URLs from search results
                    search_data = result.data
                    if isinstance(search_data, str):
                        urls = self._extract_urls_from_search(search_data)
                        
                        # Force visit top 5 pages (use source registry if not enough URLs)
                        if len(urls) < 5:
                            print(f"[REASON] Only found {len(urls)} URLs, using source registry for more")
                            
                            original_query = subtask["parameters"].get("query", "")
                            
                            try:
                                from src.routing.source_registry import get_source_registry
                                registry = get_source_registry()
                                sources = registry.get_sources_for_category(original_query)
                                
                                if sources:
                                    print(f"[REASON] Found {len(sources)} sources in registry")
                                    for source in sources[:5]:
                                        source_url = f"https://{source['domain']}"
                                        if source_url not in urls:
                                            urls.append(source_url)
                                            print(f"[REASON] Added source: {source_url}")
                                        if len(urls) >= 5:
                                            break
                            except Exception as e:
                                print(f"[REASON] Source registry lookup failed: {e}")
                        
                        urls = urls[:5]
                        
                        if urls:
                            required_fields = plan.get("required_fields", [])
                            
                            # 🚀 USE PARALLEL EXTRACTION HERE!
                            print(f"[REASON] 🚀 Launching PARALLEL extraction from {len(urls)} URLs")
                            
                            try:
                                # Run parallel extraction
                                import asyncio
                                # Create new event loop for worker thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    parallel_results = loop.run_until_complete(
                                        self._execute_parallel_extraction(urls, required_fields)
                                    )
                                finally:
                                    loop.close()
                                
                                # Combine all data from parallel extractions
                                all_records = []
                                for parallel_result in parallel_results:
                                    if parallel_result.get('success') and parallel_result.get('data'):
                                        all_records.extend(parallel_result['data'])
                                        print(f"[REASON] ✅ Got {parallel_result['count']} records from {parallel_result['url']}")
                                
                                print(f"[REASON] 📊 Combined total: {len(all_records)} records from {len(parallel_results)} URLs")
                                
                                # Create a single result entry with all data
                                combined_result = {
                                    "subtask_id": f"{subtask['subtask_id']}_parallel_extract",
                                    "tool": "parallel_extraction",
                                    "success": len(all_records) > 0,
                                    "data": all_records,
                                    "metadata": {
                                        "urls_extracted": len(parallel_results),
                                        "total_records": len(all_records)
                                    }
                                }
                                
                                results.append(combined_result)
                                extraction_tasks_added = True
                                
                                print(f"[REASON] ✨ Parallel extraction complete!")
                                
                            except Exception as e:
                                print(f"[REASON] ❌ Parallel extraction failed: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print("[REASON] ⚠️ No URLs found and no sources in registry")
                
                # FIX 5C: Check completeness and create follow-up if needed
                if result.success and result.metadata:
                    is_complete = result.metadata.get("complete", True)
                    
                    if not is_complete:
                        reason = result.metadata.get("completeness_reason", "Task incomplete")
                        next_action = result.metadata.get("suggested_action", "search_more_sources")
                        coverage = result.metadata.get("coverage", "unknown")
                        
                        tool_name = subtask["tool"]
                        current_count = follow_up_counts.get(tool_name, 0)
                        
                        # Extract coverage percentage for comparison
                        try:
                            coverage_num = int(coverage.rstrip('%')) if isinstance(coverage, str) and '%' in coverage else 0
                        except:
                            coverage_num = 0
                        
                        prev_coverage = previous_coverage.get(tool_name, 0)
                        
                        print(f"[REASON] ⚠️ Subtask incomplete: {reason} (Coverage: {coverage})")
                        
                        # NEW: Reset counter if coverage improved
                        if coverage_num > prev_coverage:
                            print(f"[REASON] ✨ Coverage improved from {prev_coverage}% to {coverage_num}% - resetting retry counter")
                            follow_up_counts[tool_name] = 0
                            current_count = 0
                        
                        # Update previous coverage
                        previous_coverage[tool_name] = coverage_num
                        
                        # NEW: Check if we've hit the follow-up limit
                        if current_count < MAX_FOLLOW_UPS_PER_TOOL:
                            self.log(f"Subtask incomplete: {reason}. Creating follow-up task...")
                            
                            # Create follow-up subtask
                            follow_up = self._create_follow_up_task(
                                original_subtask=subtask,
                                result=result_entry,
                                suggested_action=next_action,
                                reason=reason
                            )
                            
                            if follow_up:
                                follow_up_counts[tool_name] = current_count + 1
                                print(f"[REASON] ➕ Adding follow-up task {current_count + 1}/{MAX_FOLLOW_UPS_PER_TOOL} for {tool_name}")
                                subtasks.append(follow_up)  # Add to queue for next iteration
                        else:
                            # Hit limit, log and continue with what we have
                            print(f"[REASON] ⚠️ Max follow-ups ({MAX_FOLLOW_UPS_PER_TOOL}) reached for {tool_name}")
                            self.log(f"Max follow-ups reached for {tool_name}, proceeding with available results")
                
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
            
            # Parse JSON with error recovery
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                
                try:
                    extracted_data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[REASON] JSON parse error: {e}, attempting to fix...")
                    # Try to fix common JSON issues
                    json_str = json_str.replace("'", '"')  # Single to double quotes
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
                    json_str = re.sub(r'(\w+):', r'"\1":', json_str)  # Quote unquoted keys
                    
                    try:
                        extracted_data = json.loads(json_str)
                        print(f"[REASON] JSON fixed and parsed successfully")
                    except:
                        print(f"[REASON] Could not fix JSON, skipping structured data storage")
                        return
                
                # Store in structured memory with timestamp
                subject = extracted_data.get("subject", f"query_{len(self.structured_memory)}")
                self.structured_memory[subject] = {
                    **extracted_data,
                    "timestamp": time.time(),
                    "query": task_description
                }
                print(f"[REASON] ✅ Stored structured data for: {subject}")
                
        except Exception as e:
            print(f"[REASON] Failed to extract structured data: {e}")
            import traceback
            traceback.print_exc()
    
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
            
            # DEBUG: Log prompt details
            print(f"[REASON] 📊 Synthesis prompt length: {len(synthesis_prompt)} chars")
            print(f"[REASON] 📊 Sending {len(successful_results)} results to LLM")
            
            # Get LLM model and invoke it (LangChain)
            model = self.llm_service.get_model()
            response = model.invoke(synthesis_prompt)
            
            # Extract content from LangChain response
            synthesized_answer = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # DEBUG: Log response details
            print(f"[REASON] 📊 LLM response length: {len(synthesized_answer)} chars")
            if synthesized_answer:
                print(f"[REASON] 📊 LLM response preview: {synthesized_answer[:200]}...")
            
            if synthesized_answer and len(synthesized_answer) > 0:
                print(f"[REASON] LLM synthesis complete ({len(synthesized_answer)} chars)")
                return synthesized_answer
            else:
                print("[REASON] ⚠️ LLM returned empty response, using fallback")
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

**IMPORTANT: All subtasks have completed successfully. Provide a complete, final answer.**

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
        
        # LIMIT: Only send top 10 results to LLM to avoid token limits
        limited_results = results[:10]
        if len(results) > 10:
            print(f"[REASON] 📊 Limiting synthesis to top 10 results (have {len(results)} total)")
        
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
        For follow-up questions, uses previous context.
        
        Args:
            task: Task to handle
            analysis: Task analysis
            
        Returns:
            Direct result
        """
        # Check if this is a follow-up question
        if self._is_followup_question(task.description):
            print("[REASON] Handling follow-up question with previous context")
            
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
    
    def _create_follow_up_task(
        self,
        original_subtask: Dict[str, Any],
        result: Dict[str, Any],
        suggested_action: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a follow-up subtask when original task is incomplete.
        Uses LLM-based source registry for intelligent query refinement.
        ZERO HARDCODING!
        
        Args:
            original_subtask: The original subtask that was incomplete
            result: Result from the incomplete subtask
            suggested_action: Suggested action from completeness evaluation
            reason: Reason for incompleteness
            
        Returns:
            Follow-up subtask dict or None
        """
        try:
            from src.routing.source_registry import get_source_registry
            
            original_tool = original_subtask["tool"]
            original_params = original_subtask["parameters"]
            
            # Create follow-up based on suggested action
            if suggested_action == "search_more_sources":
                # For searches, use source registry for intelligent follow-up
                original_query = original_params.get("query", "")
                
                if not original_query:
                    print(f"[REASON] No query in parameters, cannot create follow-up")
                    return None
                
                # Get sources using dynamic registry
                registry = get_source_registry()
                sources = registry.get_sources_for_category(original_query)
                
                if not sources:
                    print(f"[REASON] No sources available for query: {original_query}")
                    return None
                
                # Get domains already tried
                used_domains = self._get_used_domains(original_subtask)
                
                # Find next untried source
                for source in sources:
                    if source["domain"] not in used_domains:
                        # Use source for refined query (append site: operator)
                        refined_query = f"{original_query} site:{source['domain']}"
                        
                        print(f"[REASON] Next source: {source['domain']} (reliability: {source['reliability']})")
                        print(f"[REASON] Refined query: {refined_query}")
                        
                        follow_up = {
                            "subtask_id": f"{original_subtask['subtask_id']}_followup",
                            "tool": original_tool,
                            "parameters": {
                                **original_params,
                                "query": refined_query
                            },
                            "description": f"Search {source['domain']}: {refined_query}",
                            "metadata": {
                                "source": source["domain"],
                                "domain": source["domain"],
                                "reliability": source["reliability"]
                            }
                        }
                        
                        return follow_up
                
                # All sources exhausted
                print(f"[REASON] All sources exhausted for content type")
                return None
            
            elif suggested_action == "extract_more_details":
                # For extraction, try to get missing fields
                # Could switch to a more detailed extraction tool
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
            print(f"[REASON] No specific follow-up strategy for action: {suggested_action}")
            return None
            
        except Exception as e:
            print(f"[REASON] Error creating follow-up task: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_used_domains(self, subtask: Dict[str, Any]) -> List[str]:
        """
        Extract domains already tried from subtask history.
        Tracks which sources have been attempted.
        
        Args:
            subtask: Current subtask
            
        Returns:
            List of domain names already tried
        """
        used = []
        
        # Check if subtask has metadata with domain
        if "metadata" in subtask and "domain" in subtask["metadata"]:
            used.append(subtask["metadata"]["domain"])
        
        # Extract domain from query if it has site: operator
        query = subtask.get("parameters", {}).get("query", "")
        if "site:" in query:
            import re
            match = re.search(r'site:([^\s]+)', query)
            if match:
                used.append(match.group(1))
        
        return used
    
    def clear_context(self) -> None:
        """Clear execution context."""
        self.context.clear()
        self.execution_history.clear()
    
    def check_data_completeness(
        self,
        results: List[Dict[str, Any]],
        required_fields: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if extracted data has all required fields.
        Uses ResultValidator for intelligent completeness checking.
        
        Args:
            results: List of extracted records
            required_fields: List of required field names
            context: Optional context (url, page_type, etc.)
            
        Returns:
            {
                'complete': bool,
                'missing_fields': List[str],
                'coverage': float (0.0-1.0),
                'confidence': float (0.0-1.0),
                'suggested_actions': List[Dict]
            }
        """
        try:
            from src.routing.result_validator import ResultValidator
            
            validator = ResultValidator()
            validation = validator.validate(results, required_fields, context)
            
            print(f"[REASON] ✅ Data completeness check:")
            print(f"  - Complete: {validation['complete']}")
            print(f"  - Coverage: {validation['coverage']*100:.0f}%")
            print(f"  - Confidence: {validation['confidence']*100:.0f}%")
            if validation['missing_fields']:
                print(f"  - Missing: {validation['missing_fields']}")
            
            return validation
            
        except Exception as e:
            print(f"[REASON] Completeness check failed: {e}")
            # Fallback
            if not results:
                return {
                    'complete': False,
                    'missing_fields': required_fields,
                    'coverage': 0.0,
                    'confidence': 0.0,
                    'suggested_actions': []
                }
            
            present_fields = set(results[0].keys())
            required_set = set(required_fields)
            missing = list(required_set - present_fields)
            coverage = len(present_fields & required_set) / len(required_set) if required_set else 1.0
            
            return {
                'complete': len(missing) == 0,
                'missing_fields': missing,
                'coverage': coverage,
                'confidence': 0.5,
                'suggested_actions': []
            }
    
    def plan_multi_step_extraction(
        self,
        initial_results: List[Dict[str, Any]],
        required_fields: List[str],
        url: str,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        Plan multi-step extraction when initial results are incomplete.
        Creates click-through and navigation tasks to gather missing data.
        
        Args:
            initial_results: Initial extraction results (incomplete)
            required_fields: List of required field names
            url: Current URL
            task_id: Base task ID for generating subtask IDs
            
        Returns:
            List of additional subtasks to execute
        """
        print(f"[REASON] 🎯 Planning multi-step extraction for missing fields")
        
        try:
            from src.routing.result_validator import ResultValidator
            
            # Check what's missing
            validator = ResultValidator()
            validation = validator.validate(
                initial_results,
                required_fields,
                {'url': url}
            )
            
            if validation['complete']:
                print(f"[REASON] Data is already complete, no multi-step needed")
                return []
            
            missing_fields = validation['missing_fields']
            suggested_actions = validation['suggested_actions']
            
            print(f"[REASON] Missing fields: {missing_fields}")
            print(f"[REASON] Suggested actions: {len(suggested_actions)}")
            
            # Convert suggestions to subtasks
            additional_tasks = []
            
            for i, action in enumerate(suggested_actions):
                action_type = action.get('action')
                field = action.get('field')
                
                if action_type == 'click_through':
                    # Create click-through task sequence
                    # 1. Find and click product/item link
                    # 2. Extract missing field from detail page
                    # 3. Go back
                    
                    # Click task
                    click_task = {
                        'subtask_id': f"{task_id}_click_{i}",
                        'tool': 'playwright_execute',
                        'parameters': {
                            'method': 'click',
                            'selector': 'a[class*="item"], a[class*="product"], a[class*="title"]',
                            'args': {'index': 0}  # Click first item
                        },
                        'description': f"Click product link to get {field}"
                    }
                    additional_tasks.append(click_task)
                    
                    # Extract task
                    extract_task = {
                        'subtask_id': f"{task_id}_extract_detail_{i}",
                        'tool': 'playwright_execute',
                        'parameters': {
                            'method': 'extract_chart',
                            'required_fields': [field]
                        },
                        'description': f"Extract {field} from detail page"
                    }
                    additional_tasks.append(extract_task)
                    
                    # Go back task
                    back_task = {
                        'subtask_id': f"{task_id}_back_{i}",
                        'tool': 'playwright_execute',
                        'parameters': {
                            'method': 'go_back',
                            'args': {}
                        },
                        'description': "Go back to listing"
                    }
                    additional_tasks.append(back_task)
                
                elif action_type == 'navigate':
                    # Navigate to different page
                    target = action.get('target')
                    nav_task = {
                        'subtask_id': f"{task_id}_nav_{i}",
                        'tool': 'playwright_execute',
                        'parameters': {
                            'method': 'click',
                            'selector': f'a[href*="{target}"]',
                            'args': {}
                        },
                        'description': f"Navigate to {target} page"
                    }
                    additional_tasks.append(nav_task)
                    
                    # Extract from new page
                    extract_task = {
                        'subtask_id': f"{task_id}_extract_{i}",
                        'tool': 'playwright_execute',
                        'parameters': {
                            'method': 'extract_chart',
                            'required_fields': [field]
                        },
                        'description': f"Extract {field} from {target} page"
                    }
                    additional_tasks.append(extract_task)
            
            if additional_tasks:
                print(f"[REASON] ✅ Created {len(additional_tasks)} additional extraction tasks")
            else:
                print(f"[REASON] ⚠️ No additional tasks could be created")
            
            return additional_tasks
            
        except Exception as e:
            print(f"[REASON] Multi-step planning failed: {e}")
            import traceback
            traceback.print_exc()
            return []
