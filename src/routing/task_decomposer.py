"""
LLM-Based Task Decomposer

Uses LLM to decompose user tasks into structured subtasks
based on the tool registry capabilities.
Uses DataFlowResolver for schema-based parameter mapping.
"""

import json
import re
from typing import List, Dict, Any, Optional
from src.routing.tool_capabilities import format_registry_for_llm
from src.core.data_flow_resolver import get_resolver


class TaskDecomposer:
    """
    Decomposes user tasks into structured subtasks using LLM.
    
    This replaces hard-coded regex patterns with intelligent
    LLM-based task understanding and decomposition.
    """
    
    def __init__(self, llm_service: Any):
        """
        Initialize task decomposer.
        
        Args:
            llm_service: LLM service for task decomposition
        """
        self.llm_service = llm_service
        self._registry_text = format_registry_for_llm()
    
    def decompose(self, task_description: str, task_id: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Decompose a task into structured subtasks with completeness awareness.
        Uses pre-analyzed task structure from context when available to avoid extra LLM calls.
        
        Args:
            task_description: User's task description
            task_id: Unique task identifier
            context: Optional context with query_params, task_type, task_structure, etc.
            
        Returns:
            List of subtask dictionaries with tool, action, parameters
        """
        print(f"[DECOMPOSER] Decomposing task: {task_description}")
        
        # Extract context if provided
        query_params = context.get("query_params", {}) if context else {}
        task_type = context.get("task_type", "general") if context else "general"
        task_structure = context.get("task_structure", {}) if context else {}
        required_fields = context.get("required_fields", []) if context else []
        
        if query_params:
            print(f"[DECOMPOSER] Using query params from context: {query_params}")
        if task_type != "general":
            print(f"[DECOMPOSER] Task type from context: {task_type}")
        if task_structure and task_structure.get("type") != "single":
            print(f"[DECOMPOSER] Using pre-analyzed task structure: {task_structure.get('type')}")
        
        # Check if we have pre-analyzed steps (saves LLM call!) - type-agnostic
        if task_structure.get("steps"):
            structure_type = task_structure.get("type", "unknown")
            print(f"[DECOMPOSER] ⚡ Using pre-analyzed steps (type: {structure_type}, no LLM call)")
            
            # DEBUG LOGGING
            print(f"[DECOMPOSER] 🔍 DEBUG: task_structure = {task_structure}")
            print(f"[DECOMPOSER] 🔍 DEBUG: steps = {task_structure.get('steps')}")
            print(f"[DECOMPOSER] 🔍 DEBUG: steps type = {type(task_structure.get('steps'))}")
            print(f"[DECOMPOSER] 🔍 DEBUG: steps length = {len(task_structure.get('steps', []))}")
            
            return self._create_sequential_subtasks(
                task_structure.get("steps", []),
                task_id,
                query_params,
                required_fields,
                task_description  # Pass original description!
            )
        
        # Extract required fields from task description if not provided
        if not required_fields:
            required_fields = self._extract_required_fields(task_description)
            if required_fields:
                print(f"[DECOMPOSER] Detected required fields: {required_fields}")
        
        if not self.llm_service:
            print("[DECOMPOSER] No LLM service, using keyword fallback")
            return self._fallback_decomposition(task_description, task_id, query_params, task_type)
        
        try:
            subtasks = self._llm_decomposition(task_description, task_id, query_params, task_type)
            
            if subtasks:
                print(f"[DECOMPOSER] LLM generated {len(subtasks)} subtasks")
                
                # NEW: Add completeness check after extraction subtasks
                if required_fields:
                    subtasks = self._add_completeness_checks(subtasks, required_fields, task_id)
                
                # NEW: Apply query params to subtasks if api_call tool is used
                if query_params:
                    subtasks = self._apply_query_params(subtasks, query_params)
                
                return subtasks
            else:
                print("[DECOMPOSER] LLM returned empty, using fallback")
                return self._fallback_decomposition(task_description, task_id, query_params, task_type)
                
        except Exception as e:
            print(f"[DECOMPOSER] LLM decomposition failed: {e}, using fallback")
            return self._fallback_decomposition(task_description, task_id, query_params, task_type)
    
    def _llm_decomposition(self, task_description: str, task_id: str, query_params: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
        """
        Use LLM to decompose task into subtasks.
        
        Args:
            task_description: User's task description
            task_id: Unique task identifier
            
        Returns:
            List of subtask dictionaries
        """
        prompt = self._build_decomposition_prompt(task_description)
        
        model = self.llm_service.get_model()
        response = model.invoke(prompt)
        
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Extract JSON array from response
        subtasks_json = self._extract_json_array(content)
        
        if not subtasks_json:
            return []
        
        # Parse and validate
        subtasks = json.loads(subtasks_json)
        
        # Add subtask IDs and validate structure
        validated_subtasks = []
        for i, subtask in enumerate(subtasks):
            if self._validate_subtask(subtask):
                subtask["subtask_id"] = f"{task_id}_sub_{i}"
                subtask["description"] = subtask.get("description", f"Step {i+1}")
                validated_subtasks.append(subtask)
        
        return validated_subtasks
    
    def _build_decomposition_prompt(self, task_description: str) -> str:
        """
        Build prompt for LLM task decomposition.
        
        Args:
            task_description: User's task description
            
        Returns:
            Prompt string
        """
        prompt = f"""You are a task planning assistant. Decompose the user's request into a sequence of subtasks using available tools.

{self._registry_text}

---

**User Request:** "{task_description}"

**Instructions:**
1. Analyze the request and identify required actions
2. Break it into sequential subtasks
3. For each subtask, specify:
   - tool: The tool name to use
   - action: The specific action/method
   - parameters: Required parameters (method, url, selector, args, etc.)
   - description: Brief description of what this step does

**CRITICAL: Selector Best Practices**
Use ROBUST, GENERIC selectors that work across different websites:

✅ GOOD Selectors (use these patterns):
- Search boxes: "input[name*='search' i], input[placeholder*='search' i], input[aria-label*='search' i]"
- Submit buttons: "button[type='submit'], input[type='submit'], button:has-text('Search')"
- Text inputs: "input[type='text'], input:not([type])"
- Email fields: "input[type='email'], input[name*='email' i]"
- Password fields: "input[type='password'], input[name*='password' i]"

❌ BAD Selectors (avoid these):
- Specific IDs like "input#search" (IDs vary by site)
- Single selectors without fallbacks
- Overly specific class names

**Selector Pattern Rules:**
1. Use attribute partial matching with *= for flexibility
2. Add 'i' flag for case-insensitive matching
3. Provide multiple fallback selectors with commas
4. Prefer name/type attributes over IDs
5. Use generic patterns that work across sites

**CRITICAL: Search Submission Best Practice**
For search boxes, ALWAYS use "press Enter" instead of clicking search buttons:
- ✅ More reliable (works on 99% of sites)
- ✅ Faster and simpler
- ✅ Handles JavaScript-heavy sites better
- ❌ Avoid clicking search buttons (they often don't trigger properly)

**Real-World Examples:**

Example 1 - YouTube Search (CORRECT WAY):
Step 1: Fill search box
{{
  "tool": "playwright_execute",
  "method": "fill",
  "selector": "input[name='search_query'], input[aria-label*='search' i], ytd-searchbox input",
  "args": {{"value": "cats"}}
}}
Step 2: Press Enter (ALWAYS DO THIS for searches)
{{
  "tool": "playwright_execute",
  "method": "press",
  "selector": "input[name='search_query'], input[aria-label*='search' i], ytd-searchbox input",
  "args": {{"key": "Enter"}}
}}

Example 2 - Google Search (CORRECT WAY):
Step 1: Fill search box
{{
  "tool": "playwright_execute",
  "method": "fill",
  "selector": "input[name='q'], textarea[name='q'], input[title*='search' i]",
  "args": {{"value": "python tutorials"}}
}}
Step 2: Press Enter
{{
  "tool": "playwright_execute",
  "method": "press",
  "selector": "input[name='q'], textarea[name='q']",
  "args": {{"key": "Enter"}}
}}

Example 3 - Generic Form Submit (when NOT a search):
{{
  "tool": "playwright_execute",
  "method": "click",
  "selector": "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Go')"
}}

**CRITICAL: Use Selector Hints (Preferred)**
Instead of writing raw CSS selectors, use semantic selector_hint for common elements:

Available selector hints:
- "search_input" - For search boxes on any site
- "login_button" - For login/sign in buttons
- "submit_button" - For form submit buttons
- "email_field" - For email input fields
- "password_field" - For password fields
- "username_field" - For username fields

✅ PREFERRED: Use selector_hint
{{
  "tool": "playwright_execute",
  "method": "fill",
  "selector_hint": "search_input",  # ← Use this!
  "args": {{"value": "cats"}}
}}

❌ AVOID: Raw selectors (only if no hint matches)
{{
  "tool": "playwright_execute",
  "method": "fill",
  "selector": "input[name='search']",  # Only use if no hint exists
  "args": {{"value": "cats"}}
}}

**Important Guidelines:**
- For playwright_execute, ALWAYS include "method" in parameters
- For navigation, use method="goto" with url parameter
- For common elements, use selector_hint (preferred) over raw selector
- For filling fields, use method="fill" with selector_hint or selector and args.value
- For clicking, use method="click" with selector_hint or selector
- For pressing keys, use method="press" with selector and args.key
- **CRITICAL: After clicks that navigate to new pages, add wait_for_load_state**
- For content extraction after navigation, use method="wait_for_load_state" then "inner_text" or "text_content"
- Break complex tasks into multiple simple steps

**Navigation & Content Extraction Pattern:**
When clicking a link/button that navigates to a new page, follow this pattern:

Step 1: Click the element
{{
  "tool": "playwright_execute",
  "method": "click",
  "selector": "a:has-text('FAQ')"
}}

Step 2: Wait 3 seconds for page to load (CRITICAL!)
{{
  "tool": "playwright_execute",
  "method": "wait_for_timeout",
  "args": {{"timeout": 3000}}
}}

Step 3: Close any popups/modals (CRITICAL! Many sites show login/signup modals)
{{
  "tool": "playwright_execute",
  "method": "press",
  "selector": "body",
  "args": {{"key": "Escape"}}
}}

Step 4: Extract content from loaded page
{{
  "tool": "playwright_execute",
  "method": "text_content",
  "selector": "body"  // or more specific selector
}}

**CRITICAL: Popup/Modal Handling**
Many sites (Amazon, Goodreads, etc.) show popups after navigation. ALWAYS add this step after waiting:
- Press Escape key on body element to close modals
- This prevents "element intercepts pointer events" errors
- Add this BEFORE any clicks on the new page

**CRITICAL: URL Format**
ALL URLs must include the protocol (https:// or http://):
- ✅ CORRECT: "https://example.com"
- ✅ CORRECT: "https://httpbin.org/forms/post"
- ❌ WRONG: "example.com"
- ❌ WRONG: "httpbin.org/forms/post"

**Output Format:**
Return ONLY a valid JSON array with NO explanations, NO markdown, NO code blocks.

**CRITICAL JSON Rules:**
1. All strings MUST use double quotes (not single quotes)
2. Escape special characters in strings (use \\" for quotes inside strings)
3. NO trailing commas after last item in objects/arrays
4. NO comments in JSON
5. Ensure all brackets and braces are properly closed

**Example Output:**
[{{"tool":"google_search","action":"query","parameters":{{"query":"cats"}},"description":"Search for cats"}},{{"tool":"playwright_execute","action":"goto","parameters":{{"url":"https://example.com","method":"goto","args":{{}}}},"description":"Navigate to example.com"}}]

Return ONLY the JSON array (no markdown, no explanation):"""
        
        return prompt
    
    def _extract_json_array(self, text: str) -> Optional[str]:
        """
        Extract JSON array from LLM response.
        
        Args:
            text: LLM response text
            
        Returns:
            JSON array string or None
        """
        # Try to find JSON array in code blocks
        code_block_pattern = r'```(?:json)?\s*(\[.*?\])\s*```'
        match = re.search(code_block_pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        
        # Try to find JSON array directly
        array_pattern = r'\[.*?\]'
        match = re.search(array_pattern, text, re.DOTALL)
        if match:
            return match.group(0)
        
        return None
    
    def _validate_subtask(self, subtask: Dict[str, Any]) -> bool:
        """
        Validate subtask structure.
        
        Args:
            subtask: Subtask dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ["tool", "parameters"]
        
        if not all(field in subtask for field in required_fields):
            print(f"[DECOMPOSER] Invalid subtask - missing required fields: {subtask}")
            return False
        
        # Validate playwright_execute has method
        if subtask["tool"] == "playwright_execute":
            # Accept method at top level OR inside parameters
            has_method = "method" in subtask or "method" in subtask["parameters"]
            if not has_method:
                print(f"[DECOMPOSER] Invalid playwright subtask - missing method: {subtask}")
                return False
            
            # If method is at top level, move it to parameters
            if "method" in subtask and "method" not in subtask["parameters"]:
                subtask["parameters"]["method"] = subtask.pop("method")
                print(f"[DECOMPOSER] Moved method to parameters: {subtask['parameters']['method']}")
        
        return True
    
    def _create_sequential_subtasks(
        self,
        steps: List,
        task_id: str,
        query_params: Dict[str, Any],
        required_fields: List[str],
        original_description: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Create subtasks from pre-analyzed sequential steps with tool assignments.
        Steps are expected to be objects with "description" and "tool" fields.
        Intelligently maps step descriptions to proper tool parameters.
        
        Args:
            steps: List of step objects from comprehensive analysis
            task_id: Task identifier
            query_params: Query parameters to apply
            required_fields: Fields to extract
            original_description: Original user task description (for URL extraction)
            
        Returns:
            List of subtask dictionaries
        """
        print(f"[DECOMPOSER] Creating {len(steps)} sequential subtasks with tool assignments")
        
        subtasks = []
        
        for i, step in enumerate(steps):
            # Expect step to be a dict with "description", "tool", and optionally "parameters"
            if isinstance(step, dict):
                step_desc = step.get("description", str(step))
                tool = step.get("tool", "google_search")
                print(f"[DECOMPOSER] Step {i+1}: {step_desc[:50]}... → {tool}")
                
                # Get LLM-provided parameters (may be incomplete)
                llm_params = step.get("parameters", {})
                
                # ALWAYS call schema-based mapping to fill gaps from context
                schema_params = self._map_parameters_for_tool(
                    tool, 
                    step_desc, 
                    query_params, 
                    required_fields,  # ← From context
                    original_description
                )
                
                # Merge: Schema provides defaults/required, LLM overrides with specifics
                parameters = {**schema_params, **llm_params}
                
                print(f"[DECOMPOSER] ✓ Merged parameters (schema + LLM): {parameters}")
            else:
                # Fallback for unexpected format
                step_desc = str(step)
                tool = "google_search"
                print(f"[DECOMPOSER] ⚠️ Step {i+1}: Unexpected format, using fallback → {tool}")
                parameters = self._map_parameters_for_tool(
                    tool, 
                    step_desc, 
                    query_params, 
                    required_fields,
                    original_description
                )
            
            subtask = {
                "subtask_id": f"{task_id}_seq_{i}",
                "tool": tool,
                "parameters": parameters,
                "description": step_desc
            }
            
            # Add dependency if not first step
            if i > 0:
                subtask["depends_on"] = f"{task_id}_seq_{i-1}"
            
            subtasks.append(subtask)
        
        print(f"[DECOMPOSER] ✓ Created {len(subtasks)} subtasks with tool assignments")
        return subtasks
    
    def _map_parameters_for_tool(
        self,
        tool: str,
        step_desc: str,
        query_params: Dict[str, Any],
        required_fields: List[str],
        original_description: str = ""
    ) -> Dict[str, Any]:
        """
        Map step description to proper tool parameters using schema.
        ZERO HARDCODING - uses tool_io_schema.json for all mappings.
        
        Args:
            tool: Tool name
            step_desc: Step description
            query_params: Query parameters from analysis
            required_fields: Required fields from analysis
            original_description: Original user task description
            
        Returns:
            Tool-specific parameters dict
        """
        resolver = get_resolver()
        
        # Get tool's input schema
        tool_inputs = resolver.get_tool_inputs(tool)
        
        if not tool_inputs:
            # No schema, return minimal params
            print(f"[DECOMPOSER] No schema for {tool}, using step description as query")
            return {"query": step_desc}
        
        params = {}
        
        # For each input in schema, try to provide a value
        for input_name, input_spec in tool_inputs.items():
            # Skip if not required and we can't infer a value
            if not input_spec.get("required", False):
                # Add defaults if specified
                if "default" in input_spec:
                    params[input_name] = input_spec["default"]
                continue
            
            # Map based on input type and context
            input_type = input_spec.get("type")
            
            if input_name == "query":
                # Query input - use step description
                params["query"] = step_desc
            
            elif input_name == "url":
                # URL input - extract from descriptions
                url = self._extract_url(step_desc, original_description)
                if url:
                    params["url"] = url
            
            elif input_name == "required_fields":
                # Required fields - use from analysis
                if required_fields:
                    params["required_fields"] = required_fields
            
            elif input_name == "limit":
                # Limit - use from query_params
                if query_params.get("limit"):
                    params["limit"] = query_params["limit"]
            
            elif input_name == "method":
                # Method for playwright - default to goto
                params["method"] = "goto"
            
            elif input_name == "params":
                # Query params for API calls
                if query_params:
                    params["params"] = query_params
            
            elif input_name == "args":
                # Args - default to empty dict
                params["args"] = {}
        
        # If no params were set, provide minimal fallback
        if not params:
            params = {"query": step_desc}
        
        return params
    
    def _extract_url(self, step_desc: str, original_desc: str = "") -> Optional[str]:
        """
        Extract URL from descriptions (schema-agnostic helper).
        
        Args:
            step_desc: Step description
            original_desc: Original task description
            
        Returns:
            Extracted URL or None
        """
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        
        # Try step description first
        match = re.search(url_pattern, step_desc)
        if match:
            url = match.group(0).rstrip(',.;:!?')
            print(f"[DECOMPOSER] ✓ Found URL in step: {url}")
            return url
        
        # Try original description
        if original_desc:
            match = re.search(url_pattern, original_desc)
            if match:
                url = match.group(0).rstrip(',.;:!?')
                print(f"[DECOMPOSER] ✓ Found URL in original: {url}")
                return url
        
        return None
    
    def _apply_query_params(self, subtasks: List[Dict[str, Any]], query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply query parameters to subtasks that use api_call or need params.
        
        Args:
            subtasks: List of subtasks
            query_params: Query parameters to apply
            
        Returns:
            Updated subtasks with query params
        """
        for subtask in subtasks:
            tool = subtask.get("tool")
            
            # Apply to api_call tool
            if tool == "api_call":
                if "parameters" not in subtask:
                    subtask["parameters"] = {}
                if "params" not in subtask["parameters"]:
                    subtask["parameters"]["params"] = query_params
                    print(f"[DECOMPOSER] Applied query params to api_call: {query_params}")
            
            # Apply to playwright_execute for API URLs
            elif tool == "playwright_execute":
                params = subtask.get("parameters", {})
                url = params.get("url", "")
                
                # If URL looks like an API endpoint, add query params
                if "api" in url.lower() or "/posts" in url or "/users" in url:
                    # Build query string
                    if query_params:
                        query_str = "&".join([f"{k}={v}" for k, v in query_params.items()])
                        if "?" in url:
                            params["url"] = f"{url}&{query_str}"
                        else:
                            params["url"] = f"{url}?{query_str}"
                        print(f"[DECOMPOSER] Applied query params to URL: {params['url']}")
        
        return subtasks
    
    def _fallback_decomposition(self, task_description: str, task_id: str, query_params: Dict[str, Any] = {}, task_type: str = "general") -> List[Dict[str, Any]]:
        """
        Fallback decomposition using keyword matching.
        
        Args:
            task_description: User's task description
            task_id: Unique task identifier
            
        Returns:
            List of subtask dictionaries
        """
        print("[DECOMPOSER] Using keyword-based fallback")
        
        description_lower = task_description.lower()
        subtasks = []
        counter = 0
        
        # Check for "go to X page" pattern (e.g., "go to battlefield 6 page")
        goto_page_pattern = r'(?:go\s+to|navigate\s+to|visit)\s+([^,\.]+?)\s+page'
        goto_match = re.search(goto_page_pattern, description_lower, re.IGNORECASE)
        
        if goto_match:
            # Extract the target (e.g., "battlefield 6")
            target = goto_match.group(1).strip()
            print(f"[DECOMPOSER] Detected 'go to page' pattern: {target}")
            
            # Use Google search to find the page
            subtasks.append({
                "subtask_id": f"{task_id}_sub_{counter}",
                "tool": "google_search",
                "action": "query",
                "parameters": {
                    "query": f"{target} official page"
                },
                "description": f"Search for {target} page"
            })
            counter += 1
            
            # Note: The agent will extract URLs from search and visit them
            return subtasks
        
        # Check for browser automation keywords
        browser_keywords = ["go to", "navigate", "visit", "click", "fill", "search", "submit"]
        
        if any(keyword in description_lower for keyword in browser_keywords):
            # Extract URL if present (full URL with domain)
            url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}(?:/[^\s]*)?'
            url_match = re.search(url_pattern, task_description)
            
            if url_match:
                url = url_match.group(0).rstrip(',.;:!?')
                # Always ensure protocol is present
                if not url.startswith(('http://', 'https://')):
                    url = f'https://{url}'
                
                print(f"[DECOMPOSER] Extracted and formatted URL: {url}")
                
                # Add navigation subtask
                subtasks.append({
                    "subtask_id": f"{task_id}_sub_{counter}",
                    "tool": "playwright_execute",
                    "action": "goto",
                    "parameters": {
                        "url": url,
                        "method": "goto",
                        "args": {}
                    },
                    "description": f"Navigate to {url}"
                })
                counter += 1
            else:
                # Try to extract website name (e.g., "go to eventbrite")
                website_pattern = r'(?:go\s+to|navigate\s+to|visit)\s+([a-zA-Z0-9]+)(?:\s|$|,)'
                website_match = re.search(website_pattern, description_lower)
                
                if website_match:
                    website_name = website_match.group(1).strip()
                    # Common website names to full domains
                    url = f'https://www.{website_name}.com'
                    
                    print(f"[DECOMPOSER] Extracted website name '{website_name}', constructed URL: {url}")
                    
                    # Add navigation subtask
                    subtasks.append({
                        "subtask_id": f"{task_id}_sub_{counter}",
                        "tool": "playwright_execute",
                        "action": "goto",
                        "parameters": {
                            "url": url,
                            "method": "goto",
                            "args": {}
                        },
                        "description": f"Navigate to {url}"
                    })
                    counter += 1
            
            # Check for search action
            if "search" in description_lower:
                search_pattern = r'search\s+(?:for\s+)?["\']?([^"\']+?)["\']?(?:\s+|$)'
                search_match = re.search(search_pattern, task_description, re.IGNORECASE)
                
                if search_match:
                    query = search_match.group(1).strip()
                    query = re.sub(r'\s+(?:and|then|,).*$', '', query, flags=re.IGNORECASE)
                    
                    subtasks.append({
                        "subtask_id": f"{task_id}_sub_{counter}",
                        "tool": "playwright_execute",
                        "action": "fill",
                        "parameters": {
                            "method": "fill",
                            "selector": "input[name='search']",
                            "args": {"value": query}
                        },
                        "description": f"Enter search: {query}"
                    })
                    counter += 1
                    
                    subtasks.append({
                        "subtask_id": f"{task_id}_sub_{counter}",
                        "tool": "playwright_execute",
                        "action": "press",
                        "parameters": {
                            "method": "press",
                            "selector": "input[name='search']",
                            "args": {"key": "Enter"}
                        },
                        "description": "Submit search"
                    })
                    counter += 1
        
        # Check for search engine queries
        elif any(keyword in description_lower for keyword in ["search", "find", "look up", "google"]):
            subtasks.append({
                "subtask_id": f"{task_id}_sub_{counter}",
                "tool": "google_search",
                "action": "query",
                "parameters": {
                    "query": task_description
                },
                "description": f"Search for: {task_description}"
            })
        
        return subtasks if subtasks else []
    
    def _extract_required_fields(self, task_description: str) -> List[str]:
        """
        Extract required fields from task description using LLM.
        NO hardcoding - LLM determines what fields are needed!
        
        Args:
            task_description: User's task description
            
        Returns:
            List of required field names
        """
        if not self.llm_service:
            # Fallback: return empty if no LLM
            return []
        
        try:
            prompt = f"""Extract the data fields requested in this query.

Query: "{task_description}"

Return ONLY a JSON array of field names the user wants:
["field1", "field2", ...]

Examples:
- "Find restaurants with name and phone" → ["name", "phone"]
- "Get product title, price, rating" → ["title", "price", "rating"]
- "List hotels with location and website" → ["location", "website"]

Return ONLY the JSON array (no explanation):"""
            
            model = self.llm_service.get_model()
            response = model.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                fields = json.loads(json_match.group())
                if isinstance(fields, list):
                    return fields
            
            return []
            
        except Exception as e:
            print(f"[DECOMPOSER] LLM field extraction failed: {e}")
            return []
    
    def _add_completeness_checks(
        self,
        subtasks: List[Dict[str, Any]],
        required_fields: List[str],
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        Add completeness check steps after extraction subtasks.
        
        Args:
            subtasks: Original subtasks
            required_fields: Required field names
            task_id: Task identifier
            
        Returns:
            Updated subtasks with completeness checks
        """
        # Find extraction subtasks (extract_chart, extract_data, etc.)
        extraction_indices = []
        for i, subtask in enumerate(subtasks):
            method = subtask.get('parameters', {}).get('method', '')
            if 'extract' in method.lower():
                extraction_indices.append(i)
        
        if not extraction_indices:
            # No extraction tasks, nothing to check
            return subtasks
        
        # Add completeness metadata to extraction tasks
        for idx in extraction_indices:
            if 'metadata' not in subtasks[idx]:
                subtasks[idx]['metadata'] = {}
            subtasks[idx]['metadata']['required_fields'] = required_fields
            subtasks[idx]['metadata']['check_completeness'] = True
        
        print(f"[DECOMPOSER] Added completeness checks for {len(required_fields)} fields")
        
        return subtasks


def create_decomposer(llm_service: Any) -> TaskDecomposer:
    """
    Factory function to create a task decomposer.
    
    Args:
        llm_service: LLM service instance
        
    Returns:
        TaskDecomposer instance
    """
    return TaskDecomposer(llm_service)
