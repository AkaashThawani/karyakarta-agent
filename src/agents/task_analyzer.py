"""
Task Analyzer Component

Responsible for analyzing tasks, selecting appropriate tools,
and extracting required fields and parameters.
"""

from typing import List, Dict, Any, Optional
from src.routing.task_decomposer import create_decomposer
from src.routing.tool_capabilities import get_tool_registry
from datetime import datetime
import json


class TaskAnalysis:
    """Data model for task analysis results."""

    def __init__(
        self,
        task_type: str = "general",
        detected_type: str = "general",
        complexity: str = "simple",
        required_tools: Optional[List[str]] = None,
        estimated_steps: int = 0,
        query_params: Optional[Dict[str, Any]] = None,
        required_fields: Optional[List[str]] = None,
        task_structure: Optional[Dict[str, Any]] = None
    ):
        self.task_type = task_type
        self.detected_type = detected_type
        self.complexity = complexity
        self.required_tools = required_tools or []
        self.estimated_steps = estimated_steps
        self.query_params = query_params or {}
        self.required_fields = required_fields or []
        self.task_structure = task_structure or {"type": "single"}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_type": self.task_type,
            "detected_type": self.detected_type,
            "complexity": self.complexity,
            "required_tools": self.required_tools,
            "estimated_steps": self.estimated_steps,
            "query_params": self.query_params,
            "required_fields": self.required_fields,
            "task_structure": self.task_structure
        }


class TaskAnalyzer:
    """
    Component responsible for analyzing tasks and determining execution requirements.

    Handles:
    - Task type detection
    - Tool selection
    - Field extraction
    - Parameter extraction
    - Complexity assessment
    """

    def __init__(self, llm_service: Any = None):
        """
        Initialize TaskAnalyzer.

        Args:
            llm_service: LLM service for analysis
        """
        self.llm_service = llm_service
        self._tool_descriptions: Optional[Dict[str, str]] = None
        self.task_decomposer = create_decomposer(llm_service) if llm_service else None

    def analyze_task(self, task_description: str) -> TaskAnalysis:
        """
        Analyze task comprehensively using LLM-based analysis.

        Args:
            task_description: Description of the task to analyze

        Returns:
            TaskAnalysis object with complete analysis
        """
        # Use comprehensive analysis (1 LLM call instead of 4)
        comprehensive = self._analyze_task_comprehensive(task_description)

        if comprehensive:
            # Got analysis from LLM
            analysis = TaskAnalysis(
                task_type=comprehensive.get("task_type", "general"),
                detected_type=comprehensive.get("task_type", "general"),
                complexity="simple" if len(comprehensive.get("required_tools", [])) <= 2 else "complex",
                required_tools=comprehensive.get("required_tools", []),
                estimated_steps=len(comprehensive.get("required_tools", [])),
                query_params=comprehensive.get("query_params", {}),
                required_fields=comprehensive.get("required_fields", []),
                task_structure=comprehensive.get("task_structure", {"type": "single"})
            )
        else:
            # Fallback to simple analysis if LLM fails
            required_tools = self._identify_required_tools_fallback(task_description)
            analysis = TaskAnalysis(
                task_type="general",
                detected_type="general",
                complexity="simple" if len(required_tools) <= 2 else "complex",
                required_tools=required_tools,
                estimated_steps=len(required_tools),
                query_params={},
                required_fields=[],
                task_structure={"type": "single"}
            )

        return analysis

    def _analyze_task_comprehensive(self, task_description: str) -> Optional[Dict[str, Any]]:
        """
        SINGLE comprehensive LLM call for complete task analysis.
        Uses Gemini 2.5 structured outputs for reliable JSON responses.

        Args:
            task_description: Task description to analyze

        Returns:
            Complete analysis dict or None if LLM fails
        """
        if not self.llm_service:
            return None

        # Use existing infrastructure - load tools from registry
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
        prompt = f"""Analyze task and return structured data.

Task: "{task_description}"

Available Tools:
{tools_str}

**CRITICAL: Sequential Task Parameter Rules**

For multi-step tasks, the system AUTOMATICALLY passes data between steps:
- Step 1 outputs (URLs, data, etc.) are AUTOMATICALLY available to Step 2
- You MUST NOT include parameters in Step 2 that come from Step 1
- The DataFlowResolver handles ALL data passing automatically

**CORRECT Example:**
Steps where url parameter is omitted - system will auto-add it:
[
  {{"tool": "google_search", "parameters": {{"query": "TechCrunch AI articles"}}}},
  {{"tool": "chart_extractor", "parameters": {{"required_fields": ["headline", "author"], "limit": 5}}}}
]

**Task Planning Principles:**
1. Break complex tasks into atomic steps
2. Use sequential for known workflows, adaptive for unknown sites
3. Include all navigation and interaction steps explicitly
4. Extract search queries and form data from user requests

**For search tasks like "go to amazon and search for X":**
- Create ALL steps: navigation + search input + search button
- Use sequential structure with predefined steps
- Extract the search query from the user request"""

        try:
            print("[TASK_ANALYZER] 🎯 Comprehensive analysis with structured output")

            # Use the new structured output method
            schema = self.llm_service.get_task_analysis_schema()
            analysis = self.llm_service.invoke_with_schema(
                prompt=prompt,
                schema=schema,
                schema_name="task_analysis"
            )

            if analysis and isinstance(analysis, dict):
                # DEBUG LOGGING
                task_type = analysis.get('task_type')
                required_tools = analysis.get('required_tools', [])
                task_structure = analysis.get('task_structure', {})
                structure_type = task_structure.get('type')
                structure_steps = task_structure.get('steps')

                print(f"[TASK_ANALYZER] 🔍 DEBUG: Structured analysis from LLM:")
                print(f"[TASK_ANALYZER] 🔍   - task_type: {task_type}")
                print(f"[TASK_ANALYZER] 🔍   - required_tools: {required_tools}")
                print(f"[TASK_ANALYZER] 🔍   - task_structure: {task_structure}")
                print(f"[TASK_ANALYZER] 🔍   - task_structure.type: {structure_type}")
                print(f"[TASK_ANALYZER] 🔍   - task_structure.steps: {structure_steps}")

                print(f"[TASK_ANALYZER] ✓ Structured analysis complete: type={task_type}, tools={len(required_tools)}, structure={structure_type}")
                return analysis
            else:
                print("[TASK_ANALYZER] ✗ Structured analysis returned invalid response")
                return None

        except Exception as e:
            print(f"[TASK_ANALYZER] ✗ Structured analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _identify_required_tools_fallback(self, task_description: str) -> List[str]:
        """
        Fallback tool identification when LLM is not available.

        Args:
            task_description: Task description

        Returns:
            List of tool names
        """
        # Simple keyword-based fallback
        description_lower = task_description.lower()

        tools = []
        if any(word in description_lower for word in ["search", "find", "look for"]):
            tools.append("google_search")

        if any(word in description_lower for word in ["scrape", "extract", "get data", "website"]):
            tools.append("chart_extractor")
            tools.append("playwright_execute")

        if any(word in description_lower for word in ["go to", "navigate", "visit", "click", "fill"]):
            tools.append("playwright_execute")

        return list(set(tools))  # Remove duplicates

    def extract_required_fields(self, query: str) -> List[str]:
        """
        Use LLM with structured outputs to extract user-requested fields AND suggest additional useful fields.
        Zero hardcoding - works for any query type.

        Args:
            query: User query

        Returns:
            List of field names
        """
        prompt = f"""Analyze this query and extract field requirements.

Query: "{query}"

Consider what data fields would be most useful for this type of query."""

        try:
            if not self.llm_service:
                # Fallback
                return ["name", "description"]

            # Use structured output for reliable JSON
            schema = self.llm_service.get_field_extraction_schema()
            result = self.llm_service.invoke_with_schema(
                prompt=prompt,
                schema=schema,
                schema_name="field_extraction"
            )

            if result and isinstance(result, dict):
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

                print(f"[TASK_ANALYZER] User requested: {user_fields}")
                print(f"[TASK_ANALYZER] Suggested: {suggested_fields}")
                print(f"[TASK_ANALYZER] Final fields: {final_fields}")

                return final_fields
        except Exception as e:
            print(f"[TASK_ANALYZER] Field extraction failed: {e}")
            import traceback
            traceback.print_exc()

        # Fallback
        return ["name", "description"]

    def extract_query_params(self, description: str) -> Dict[str, Any]:
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
            content = response.content if hasattr(response, 'content') else str(response)
            content = content.strip()

            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[TASK_ANALYZER] Query param extraction failed: {e}")

        return {}

    def detect_task_type(self, description: str) -> str:
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
                print(f"[TASK_ANALYZER] Detected task type: {task_type}")
                return task_type
            else:
                print(f"[TASK_ANALYZER] Invalid task type '{task_type}', defaulting to general")
                return "general"
        except Exception as e:
            print(f"[TASK_ANALYZER] Task type detection failed: {e}")
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
        try:
            # Load from tool registry file
            import json
            from pathlib import Path
            registry_path = Path(__file__).parent.parent.parent / "tool_registry.json"
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                    # Handle flat dictionary format
                    for tool_name, tool_data in registry.items():
                        if not tool_name.startswith("_"):  # Skip disabled tools
                            desc = tool_data.get("description", f"Tool: {tool_name}")
                            descriptions[tool_name] = desc
                print(f"[TASK_ANALYZER] Loaded {len(descriptions)} tool descriptions from registry file")
        except Exception as e:
            print(f"[TASK_ANALYZER] Failed to load from registry file: {e}")

        self._tool_descriptions = descriptions
        return descriptions
