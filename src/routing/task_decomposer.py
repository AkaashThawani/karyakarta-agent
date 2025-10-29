"""
LLM-Based Task Decomposer

Uses LLM to decompose user tasks into structured subtasks
based on the tool registry capabilities.
"""

import json
import re
from typing import List, Dict, Any, Optional
from src.routing.tool_capabilities import format_registry_for_llm


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
    
    def decompose(self, task_description: str, task_id: str) -> List[Dict[str, Any]]:
        """
        Decompose a task into structured subtasks.
        
        Args:
            task_description: User's task description
            task_id: Unique task identifier
            
        Returns:
            List of subtask dictionaries with tool, action, parameters
        """
        print(f"[DECOMPOSER] Decomposing task: {task_description}")
        
        if not self.llm_service:
            print("[DECOMPOSER] No LLM service, using keyword fallback")
            return self._fallback_decomposition(task_description, task_id)
        
        try:
            subtasks = self._llm_decomposition(task_description, task_id)
            
            if subtasks:
                print(f"[DECOMPOSER] LLM generated {len(subtasks)} subtasks")
                return subtasks
            else:
                print("[DECOMPOSER] LLM returned empty, using fallback")
                return self._fallback_decomposition(task_description, task_id)
                
        except Exception as e:
            print(f"[DECOMPOSER] LLM decomposition failed: {e}, using fallback")
            return self._fallback_decomposition(task_description, task_id)
    
    def _llm_decomposition(self, task_description: str, task_id: str) -> List[Dict[str, Any]]:
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
- Break complex tasks into multiple simple steps

**CRITICAL: URL Format**
ALL URLs must include the protocol (https:// or http://):
- ✅ CORRECT: "https://example.com"
- ✅ CORRECT: "https://httpbin.org/forms/post"
- ❌ WRONG: "example.com"
- ❌ WRONG: "httpbin.org/forms/post"

**Output Format:**
Return ONLY a valid JSON array, no explanations:

```json
[
  {{
    "tool": "playwright_execute",
    "action": "goto",
    "parameters": {{
      "url": "https://example.com",
      "method": "goto",
      "args": {{}}
    }},
    "description": "Navigate to example.com"
  }}
]
```

JSON Array:"""
        
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
            if "method" not in subtask["parameters"]:
                print(f"[DECOMPOSER] Invalid playwright subtask - missing method: {subtask}")
                return False
        
        return True
    
    def _fallback_decomposition(self, task_description: str, task_id: str) -> List[Dict[str, Any]]:
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
        
        # Check for browser automation keywords
        browser_keywords = ["go to", "navigate", "visit", "click", "fill", "search", "submit"]
        
        if any(keyword in description_lower for keyword in browser_keywords):
            # Extract URL if present
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


def create_decomposer(llm_service: Any) -> TaskDecomposer:
    """
    Factory function to create a task decomposer.
    
    Args:
        llm_service: LLM service instance
        
    Returns:
        TaskDecomposer instance
    """
    return TaskDecomposer(llm_service)
