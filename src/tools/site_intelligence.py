"""
Site Intelligence Tool - Zero-Hardcoded Site Learning

Learns site structure dynamically using LLM-driven discovery.
NO hardcoded element types or categories!

Architecture:
1. Extract ALL interactive elements (no filtering)
2. LLM discovers element types and categories
3. LLM classifies each element's purpose
4. Build dynamic schema
5. Cache for future use

Example:
    intelligence = SiteIntelligenceTool(session_id, logger)
    schema = await intelligence.learn_site("https://reddit.com", page, llm_service)
    # Returns: Complete site schema with all interactive elements classified
"""

from typing import List, Dict, Any, Optional
import json
import re
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


def try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to extract and parse JSON from various formats.
    Handles code fences, malformed JSON, and other LLM quirks.
    Enhanced with aggressive JSON fixing from reason_agent.py.
    
    Args:
        raw: Raw string that may contain JSON
        
    Returns:
        Parsed JSON dict or None
    """
    if not raw:
        return None
    
    # Try to extract JSON from markdown code fences
    patterns = [
        r'```json\s*(\{.*?\})\s*```',  # ```json { } ```
        r'```json\s*(\[.*?\])\s*```',  # ```json [ ] ```
        r'```\s*(\{.*?\})\s*```',      # ``` { } ```
        r'```\s*(\[.*?\])\s*```',      # ``` [ ] ```
        r'(\{.*\})',                    # Just { }
        r'(\[.*\])',                    # Just [ ]
    ]
    
    for pattern in patterns:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            json_str = match.group(1)
            
            # Try direct parse first
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"[INTELLIGENCE] JSON parse error: {e}, attempting aggressive fixes...")
                
                # Aggressive JSON fixing (from reason_agent.py)
                try:
                    # Fix 1: Single to double quotes
                    json_str = json_str.replace("'", '"')
                    
                    # Fix 2: Remove trailing commas before closing brackets
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    
                    # Fix 3: Quote unquoted keys
                    json_str = re.sub(r'(\w+):', r'"\1":', json_str)
                    
                    # Fix 4: Remove newlines
                    json_str = re.sub(r'[\n\r]+', ' ', json_str)
                    
                    # Try parsing fixed JSON
                    result = json.loads(json_str)
                    print(f"[INTELLIGENCE] ✅ JSON fixed and parsed successfully")
                    return result
                    
                except json.JSONDecodeError:
                    print(f"[INTELLIGENCE] ❌ Could not fix JSON, skipping")
                    continue
    
    # Final attempt: try parsing the raw string as-is
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[INTELLIGENCE] ❌ No valid JSON found in response")
        return None


class SiteIntelligenceTool(BaseTool):
    """
    Zero-hardcoded site learning tool.
    Uses LLM to discover and classify all site elements.
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.cache_dir = Path(__file__).parent.parent.parent / "selector_cache"
        self.cache_dir.mkdir(exist_ok=True)
    
    @property
    def name(self) -> str:
        return "site_intelligence"
    
    @property
    def description(self) -> str:
        return """Learn site structure dynamically with zero hardcoding.
        Discovers element types and classifies their purpose using LLM."""
    
    def validate_params(self, **kwargs) -> bool:
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        # This tool is meant to be called programmatically
        return ToolResult(
            success=True,
            data="Site intelligence tool ready. Use learn_site() method.",
            metadata={}
        )
    
    async def detect_list_structures(self, page) -> Dict[str, Any]:
        """
        Detect repeating list structures (product lists, search results, etc.).
        Returns patterns for accessing 1st, nth, last items.
        
        Args:
            page: Playwright page instance
            
        Returns:
            Dictionary of detected list structures
        """
        print("[INTELLIGENCE] Detecting list structures...")
        
        lists = await page.evaluate("""
            () => {
                // Find repeating patterns - elements with same class/structure
                const allElements = Array.from(document.querySelectorAll('*'));
                const patterns = {};
                
                // Group by parent and similar structure
                allElements.forEach(el => {
                    const parent = el.parentElement;
                    if (!parent) return;
                    
                    // Handle both string and SVGAnimatedString for className
                    const parentClassName = typeof parent.className === 'string' 
                        ? parent.className 
                        : (parent.className?.baseVal || '');
                    const childClassName = typeof el.className === 'string' 
                        ? el.className 
                        : (el.className?.baseVal || '');
                    
                    const parentKey = parent.tagName + (parentClassName ? '.' + parentClassName.split(' ')[0] : '');
                    const childKey = el.tagName + (childClassName ? '.' + childClassName.split(' ')[0] : '');
                    
                    const key = parentKey + ' > ' + childKey;
                    
                    if (!patterns[key]) {
                        patterns[key] = {
                            parent: parentKey,
                            child: childKey,
                            count: 0,
                            sample: null
                        };
                    }
                    
                    patterns[key].count++;
                    if (!patterns[key].sample) {
                        patterns[key].sample = {
                            text: el.textContent?.trim().substring(0, 50),
                            selector: childKey
                        };
                    }
                });
                
                // Filter to only lists (3+ items)
                const lists = Object.entries(patterns)
                    .filter(([_, data]) => data.count >= 3)
                    .map(([pattern, data]) => ({
                        pattern: pattern,
                        count: data.count,
                        sample: data.sample,
                        // Provide selector patterns for different positions
                        selectors: {
                            first: `${data.child}:first-of-type`,
                            last: `${data.child}:last-of-type`,
                            nth: `${data.child}:nth-of-type({n})`,
                            all: data.child
                        }
                    }))
                    .sort((a, b) => b.count - a.count)
                    .slice(0, 10); // Top 10 lists
                
                return lists;
            }
        """)
        
        print(f"[INTELLIGENCE] Detected {len(lists)} list structures")
        return {"lists": lists}
    
    async def extract_all_elements(self, page) -> List[Dict[str, Any]]:
        """
        Extract ALL interactive elements with NO hardcoded assumptions.
        
        Args:
            page: Playwright page instance
            
        Returns:
            List of element dictionaries with all properties
        """
        print("[INTELLIGENCE] Extracting all interactive elements...")
        
        elements = await page.evaluate("""
            () => {
                // Helper to generate unique CSS selector
                function generateUniqueSelector(el) {
                    if (el.id) return `#${el.id}`;
                    
                    let path = [];
                    while (el.nodeType === Node.ELEMENT_NODE) {
                        let selector = el.nodeName.toLowerCase();
                        if (el.className) {
                            // Handle both string and SVGAnimatedString
                            const className = typeof el.className === 'string' 
                                ? el.className 
                                : (el.className.baseVal || '');
                            const classes = className.split(' ').filter(c => c);
                            if (classes.length > 0) {
                                selector += '.' + classes.join('.');
                            }
                        }
                        path.unshift(selector);
                        el = el.parentNode;
                        if (!el || el.nodeType !== Node.ELEMENT_NODE) break;
                        if (path.length > 4) break; // Limit depth
                    }
                    return path.join(' > ');
                }
                
                // Get EVERY element in the DOM
                const allElements = Array.from(document.querySelectorAll('*'));
                
                // Filter and extract properties
                return allElements
                    .filter(el => {
                        // Get visible elements with content OR interactive elements
                        const rect = el.getBoundingClientRect();
                        const isVisible = rect.width > 0 && rect.height > 0;
                        
                        if (!isVisible) return false;
                        
                        // Check if has meaningful content
                        const hasContent = el.textContent?.trim().length > 0;
                        
                        // Check if interactive
                        const interactiveTags = ['a', 'button', 'input', 'select', 'textarea'];
                        const isInteractive = interactiveTags.includes(el.tagName.toLowerCase()) ||
                                             el.onclick !== null ||
                                             el.getAttribute('role') === 'button' ||
                                             el.getAttribute('tabindex') !== null;
                        
                        // Check if structural (contains data)
                        const structuralTags = ['div', 'section', 'article', 'table', 'ul', 'ol', 'dl'];
                        const isStructural = structuralTags.includes(el.tagName.toLowerCase()) && 
                                           el.children.length > 2;
                        
                        // Accept if interactive OR has content OR is structural
                        return isInteractive || hasContent || isStructural;
                    })
                    .map(el => {
                        const rect = el.getBoundingClientRect();
                        
                        // Extract ALL attributes
                        const attributes = {};
                        for (let attr of el.attributes) {
                            attributes[attr.name] = attr.value;
                        }
                        
                        // Get computed styles (relevant ones)
                        const styles = window.getComputedStyle(el);
                        
                        return {
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim().substring(0, 100) || '',
                            attributes: attributes,
                            selector: generateUniqueSelector(el),
                            boundingBox: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            },
                            visible: styles.display !== 'none' && styles.visibility !== 'hidden',
                            enabled: !el.disabled
                        };
                    })
                    .filter(el => el.visible && el.enabled)
                    .slice(0, 150); // Limit for token efficiency
            }
        """)
        
        print(f"[INTELLIGENCE] Extracted {len(elements)} interactive elements")
        return elements
    
    async def discover_element_types(
        self, 
        elements: List[Dict[str, Any]], 
        llm_service
    ) -> Dict[str, Any]:
        """
        Let LLM discover what types of elements exist.
        NO HARDCODED CATEGORIES!
        
        Args:
            elements: List of extracted elements
            llm_service: LLM service for inference
            
        Returns:
            Dictionary of discovered types
        """
        print("[INTELLIGENCE] Discovering element types with LLM...")
        
        # Sample elements for analysis (token efficiency)
        sample = elements[:30]
        
        prompt = f"""You are a web scraping expert. Analyze these page elements and discover what types exist.

CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no markdown, just JSON.

Elements (sample):
{json.dumps(sample, indent=2)}

Analyze the elements and return ONLY this exact JSON structure:

{{
  "discovered_types": [
    {{
      "type_name": "search_system",
      "description": "Elements for searching content",
      "importance": "high",
      "element_indices": [0, 1, 2]
    }}
  ]
}}

EXAMPLE of correct response:
{{
  "discovered_types": [
    {{
      "type_name": "navigation_links",
      "description": "Main site navigation",
      "importance": "medium",
      "element_indices": [0, 5, 7]
    }},
    {{
      "type_name": "search_input",
      "description": "Search functionality",
      "importance": "high",
      "element_indices": [3]
    }}
  ]
}}

Your JSON response (no markdown, no explanations):"""

        try:
            model = llm_service.get_model()
            response = model.invoke(prompt)  # Changed to sync invoke
            content = response.content.strip()
            
            # Use robust JSON parser
            discovered = try_parse_json(content)
            if discovered and "discovered_types" in discovered:
                print(f"[INTELLIGENCE] Discovered {len(discovered.get('discovered_types', []))} element types")
                return discovered
            else:
                print(f"[INTELLIGENCE] ❌ LLM returned invalid JSON - returning empty types")
                return {"discovered_types": []}
                
        except Exception as e:
            print(f"[INTELLIGENCE] ❌ Type discovery failed: {e} - returning empty types")
            return {"discovered_types": []}
    
    def _fallback_discover_types(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fallback heuristic-based type discovery when LLM fails.
        
        Args:
            elements: List of extracted elements
            
        Returns:
            Dictionary of discovered types
        """
        print("[INTELLIGENCE] Using heuristic type discovery")
        
        discovered_types = []
        
        # Find input elements (search, forms)
        input_indices = []
        button_indices = []
        link_indices = []
        
        for i, el in enumerate(elements):
            tag = el.get("tag", "").lower()
            attrs = el.get("attributes", {})
            
            if tag == "input":
                input_type = attrs.get("type", "text").lower()
                if input_type in ["search", "text"]:
                    input_indices.append(i)
            elif tag == "button" or (tag == "input" and attrs.get("type") == "submit"):
                button_indices.append(i)
            elif tag == "a":
                link_indices.append(i)
        
        if input_indices:
            discovered_types.append({
                "type_name": "input_fields",
                "description": "Input fields for user interaction",
                "importance": "high",
                "element_indices": input_indices[:5]
            })
        
        if button_indices:
            discovered_types.append({
                "type_name": "action_buttons",
                "description": "Clickable buttons",
                "importance": "high",
                "element_indices": button_indices[:5]
            })
        
        if link_indices:
            discovered_types.append({
                "type_name": "navigation_links",
                "description": "Navigation and content links",
                "importance": "medium",
                "element_indices": link_indices[:10]
            })
        
        print(f"[INTELLIGENCE] Heuristic discovery found {len(discovered_types)} types")
        return {"discovered_types": discovered_types}
    
    async def classify_elements_with_llm(
        self, 
        elements: List[Dict[str, Any]], 
        llm_service
    ) -> List[Dict[str, Any]]:
        """
        Let LLM classify each element's purpose.
        NO HARDCODED RULES!
        
        Args:
            elements: List of extracted elements
            llm_service: LLM service for inference
            
        Returns:
            List of classified elements
        """
        print("[INTELLIGENCE] Classifying elements with LLM...")
        
        classified = []
        batch_size = 20
        
        for i in range(0, min(len(elements), 100), batch_size):
            batch = elements[i:i+batch_size]
            
            prompt = f"""You are a web scraping expert. Classify these page elements by their purpose.

CRITICAL: Respond with ONLY valid JSON array. No markdown, no explanations.

Elements:
{json.dumps(batch, indent=2)}

For each element, provide:
1. original_selector (from element)
2. semantic_name (descriptive, snake_case)
3. purpose (what it does)
4. category (search/navigation/form/action/content)
5. confidence (0.0-1.0)
6. reasoning (why you classified it this way)

EXAMPLE response:
[
  {{
    "original_selector": "input[name='q']",
    "semantic_name": "main_search_input",
    "purpose": "Primary search functionality",
    "category": "search",
    "confidence": 0.95,
    "reasoning": "Input with name='q', type='search'"
  }},
  {{
    "original_selector": "button[type='submit']",
    "semantic_name": "search_submit_button",
    "purpose": "Submit search query",
    "category": "action",
    "confidence": 0.90,
    "reasoning": "Submit button near search input"
  }}
]

Your JSON array response (no markdown):"""

            try:
                model = llm_service.get_model()
                response = model.invoke(prompt)  # Changed to sync invoke
                content = response.content.strip()
                
                # Use robust JSON parser
                batch_classified = try_parse_json(content)
                if batch_classified and isinstance(batch_classified, list):
                    classified.extend(batch_classified)
                    print(f"[INTELLIGENCE] Classified batch {i//batch_size + 1}: {len(batch_classified)} elements")
                else:
                    print(f"[INTELLIGENCE] ❌ Batch {i//batch_size + 1} LLM failed - skipping batch")
                    
            except Exception as e:
                print(f"[INTELLIGENCE] ❌ Batch {i//batch_size + 1} classification failed: {e} - skipping batch")
        
        print(f"[INTELLIGENCE] Total classified: {len(classified)} elements")
        return classified
    
    def _fallback_classify_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fallback heuristic-based element classification when LLM fails.
        
        Args:
            elements: List of elements to classify
            
        Returns:
            List of classified elements
        """
        print("[INTELLIGENCE] Using heuristic element classification")
        
        classified = []
        
        for element in elements:
            tag = element.get("tag", "").lower()
            attrs = element.get("attributes", {})
            text = element.get("text", "").lower()
            selector = element.get("selector", "")
            
            # Default classification
            category = "unknown"
            purpose = "Interactive element"
            semantic_name = f"{tag}_element"
            confidence = 0.5
            reasoning = f"Heuristic: {tag} tag"
            
            # Classify based on tag and attributes
            if tag == "input":
                input_type = attrs.get("type", "text").lower()
                name = attrs.get("name", "")
                placeholder = attrs.get("placeholder", "").lower()
                
                if input_type in ["search", "text"] and ("search" in name or "search" in placeholder or "q" in name):
                    category = "search"
                    semantic_name = f"search_input_{name or 'main'}"
                    purpose = "Search input field"
                    confidence = 0.8
                    reasoning = f"Input with type={input_type}, search-related attributes"
                elif input_type == "email":
                    category = "form"
                    semantic_name = f"email_input_{name or 'main'}"
                    purpose = "Email input field"
                    confidence = 0.85
                elif input_type == "password":
                    category = "form"
                    semantic_name = f"password_input_{name or 'main'}"
                    purpose = "Password input field"
                    confidence = 0.85
                else:
                    category = "form"
                    semantic_name = f"text_input_{name or 'field'}"
                    purpose = "Text input field"
                    confidence = 0.7
            
            elif tag == "button":
                button_text = text[:30]
                if "search" in text:
                    category = "search"
                    semantic_name = "search_button"
                    purpose = "Search submit button"
                    confidence = 0.8
                elif "submit" in text or attrs.get("type") == "submit":
                    category = "action"
                    semantic_name = "submit_button"
                    purpose = "Form submit button"
                    confidence = 0.75
                else:
                    category = "action"
                    semantic_name = f"button_{button_text.replace(' ', '_')}"
                    purpose = "Action button"
                    confidence = 0.6
            
            elif tag == "a":
                category = "navigation"
                link_text = text[:30].replace(" ", "_")
                semantic_name = f"link_{link_text or 'nav'}"
                purpose = "Navigation link"
                confidence = 0.7
                reasoning = "Anchor tag for navigation"
            
            elif tag == "textarea":
                name = attrs.get("name", "")
                category = "form"
                semantic_name = f"textarea_{name or 'input'}"
                purpose = "Multi-line text input"
                confidence = 0.75
            
            elif tag == "select":
                name = attrs.get("name", "")
                category = "form"
                semantic_name = f"select_{name or 'dropdown'}"
                purpose = "Dropdown selection"
                confidence = 0.75
            
            classified.append({
                "original_selector": selector,
                "semantic_name": semantic_name,
                "purpose": purpose,
                "category": category,
                "confidence": confidence,
                "reasoning": reasoning
            })
        
        return classified
    
    async def build_site_schema(
        self,
        url: str,
        page,
        llm_service
    ) -> Dict[str, Any]:
        """
        Build complete site schema with ZERO hardcoding.
        
        Args:
            url: Site URL
            page: Playwright page instance
            llm_service: LLM service
            
        Returns:
            Complete site schema
        """
        # Blacklist video sites - no point learning from them
        BLACKLISTED_DOMAINS = [
            'youtube.com',
            'youtu.be',
            'vimeo.com',
            'dailymotion.com'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        
        if any(blocked in domain for blocked in BLACKLISTED_DOMAINS):
            print(f"\n{'='*60}")
            print(f"⛔ SKIPPING BLACKLISTED DOMAIN")
            print(f"{'='*60}")
            print(f"Domain: {domain}")
            print(f"Reason: Video site - no useful structure to learn")
            print(f"{'='*60}\n")
            return self._empty_schema(url)
        
        print(f"\n{'='*60}")
        print(f"🧠 LEARNING SITE STRUCTURE")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")
        
        # Step 1: Extract everything (no assumptions)
        all_elements = await self.extract_all_elements(page)
        
        if not all_elements:
            print("[INTELLIGENCE] No interactive elements found")
            return self._empty_schema(url)
        
        # Step 2: Discover types (LLM-driven)
        discovered_types = await self.discover_element_types(all_elements, llm_service)
        
        # Step 3: Classify each element (LLM-driven)
        classified = await self.classify_elements_with_llm(all_elements, llm_service)
        
        # Step 3.5: Detect list structures (for 1st, nth, last access)
        list_structures = await self.detect_list_structures(page)
        
        # Step 4: Build schema dynamically
        schema = {
            "url": url,
            "learned_at": datetime.now().isoformat(),
            "total_elements_found": len(all_elements),
            "classified_elements": len(classified),
            "discovered_types": discovered_types.get("discovered_types", []),
            "list_structures": list_structures.get("lists", []),
            "elements": {}
        }
        
        # Group by semantic name (LLM-generated!)
        for element in classified:
            semantic_name = element.get("semantic_name")
            if semantic_name:
                schema["elements"][semantic_name] = {
                    "selector": element.get("original_selector", ""),
                    "purpose": element.get("purpose", ""),
                    "category": element.get("category", "unknown"),
                    "confidence": element.get("confidence", 0.0),
                    "reasoning": element.get("reasoning", "")
                }
        
        # Log results
        print(f"\n{'='*60}")
        print(f"✅ SITE LEARNING COMPLETE")
        print(f"{'='*60}")
        print(f"Total elements found: {len(all_elements)}")
        print(f"Elements classified: {len(classified)}")
        print(f"Discovered types: {len(discovered_types.get('discovered_types', []))}")
        print(f"List structures detected: {len(list_structures.get('lists', []))}")
        print(f"Unique elements: {len(schema['elements'])}")
        print(f"{'='*60}\n")
        
        return schema
    
    def _empty_schema(self, url: str) -> Dict[str, Any]:
        """Create empty schema when no elements found."""
        return {
            "url": url,
            "learned_at": datetime.now().isoformat(),
            "total_elements_found": 0,
            "classified_elements": 0,
            "discovered_types": [],
            "elements": {}
        }
    
    def save_schema(self, domain: str, schema: Dict[str, Any]):
        """
        Save site schema to cache.
        
        Args:
            domain: Domain name
            schema: Site schema
        """
        try:
            # Load existing cache
            cache_file = self.cache_dir / f"{domain}.json"
            
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            else:
                cache = {}
            
            # Add site intelligence section
            cache["site_intelligence"] = schema
            
            # Save
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
            
            print(f"\n{'='*60}")
            print(f"💾 SITE INTELLIGENCE SAVED")
            print(f"{'='*60}")
            print(f"Domain: {domain}")
            print(f"File: {cache_file}")
            print(f"Elements cached: {len(schema.get('elements', {}))}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"[INTELLIGENCE] Error saving schema: {e}")
    
    def load_schema(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Load site schema from cache.
        
        Args:
            domain: Domain name
            
        Returns:
            Site schema or None
        """
        try:
            cache_file = self.cache_dir / f"{domain}.json"
            
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    return cache.get("site_intelligence")
            
            return None
            
        except Exception as e:
            print(f"[INTELLIGENCE] Error loading schema: {e}")
            return None
    
    async def learn_site(
        self,
        url: str,
        page,
        llm_service
    ) -> Dict[str, Any]:
        """
        Main entry point: Learn complete site structure.
        
        Args:
            url: Site URL
            page: Playwright page instance
            llm_service: LLM service
            
        Returns:
            Complete site schema
        """
        # Extract domain
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check if already learned (and recent)
        existing = self.load_schema(domain)
        if existing:
            learned_at = datetime.fromisoformat(existing["learned_at"])
            age_days = (datetime.now() - learned_at).days
            
            if age_days < 30:  # Cache valid for 30 days
                print(f"[INTELLIGENCE] Using cached schema for {domain} (age: {age_days} days)")
                return existing
        
        # Learn site structure
        schema = await self.build_site_schema(url, page, llm_service)
        
        # Save to cache
        self.save_schema(domain, schema)
        
        return schema
    
    def get_element_selector(
        self,
        domain: str,
        semantic_name: str
    ) -> Optional[str]:
        """
        Get selector for a semantic element name.
        
        Args:
            domain: Site domain
            semantic_name: Semantic name (e.g., "search_input")
            
        Returns:
            CSS selector or None
        """
        schema = self.load_schema(domain)
        if schema:
            element = schema.get("elements", {}).get(semantic_name)
            if element:
                return element.get("selector")
        return None
    
    def get_list_selector(
        self,
        domain: str,
        position: str = "first"
    ) -> Optional[str]:
        """
        Get selector for list items (1st, nth, last).
        
        Args:
            domain: Site domain
            position: "first", "last", or "nth" (use {n} for number)
            
        Returns:
            CSS selector pattern or None
        """
        schema = self.load_schema(domain)
        if schema and "list_structures" in schema:
            lists = schema.get("list_structures", [])
            if lists:
                # Return selector for most common list (first in sorted list)
                main_list = lists[0]
                selectors = main_list.get("selectors", {})
                return selectors.get(position)
        return None
