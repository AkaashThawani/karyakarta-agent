"""
Adaptive Element Matcher - AI-Powered Element Discovery

Uses LLM + visual analysis to identify interactive elements on web pages.
Bridges semantic user intent to DOM operations with intelligent fallback.
"""

from typing import Dict, Any, List, Optional, Tuple
from playwright.async_api import Page
from urllib.parse import urlparse
from src.routing.selector_map import get_selector_map
from src.tools.element_parser import ElementParser
import asyncio
import json


class AdaptiveElementMatcher:
    """
    AI-powered element identification that understands semantic intent.

    Features:
    - LLM-powered element matching using page context
    - Semantic intent mapping (e.g., "search box" → actual input)
    - Visual element analysis with screenshot integration
    - Intelligent fallback chains using existing infrastructure
    - Learning from successful matches
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.selector_map = get_selector_map()
        self.element_parser = ElementParser()

        # Cache for LLM responses to avoid repeated calls
        self._llm_cache: Dict[str, Any] = {}

        print("[AdaptiveElementMatcher] Initialized with AI-powered element discovery")

    async def find_element(
        self,
        page: Page,
        intent: str,
        url: str,
        context_hints: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find element matching semantic intent using AI-powered analysis.

        Args:
            page: Playwright page instance
            intent: Semantic intent (e.g., "search_input", "login_button")
            url: Current page URL
            context_hints: Additional context about the page/task

        Returns:
            Element info dict or None if not found
        """
        print(f"[AdaptiveElementMatcher] Finding element for intent: '{intent}' on {url}")

        # Step 1: Check cached selectors (fastest)
        cached_result = self._check_cached_selectors(url, intent)
        if cached_result:
            print(f"[AdaptiveElementMatcher] ✅ Found cached selector: {cached_result['selector']}")
            return cached_result

        # Step 2: AI-powered element discovery
        ai_result = await self._ai_element_discovery(page, intent, url, context_hints)
        if ai_result:
            print(f"[AdaptiveElementMatcher] ✅ AI found element: {ai_result['selector']}")
            # Cache the successful result
            self._cache_successful_match(url, intent, ai_result)
            return ai_result

        # Step 3: Heuristic fallback
        heuristic_result = await self._heuristic_fallback(page, intent)
        if heuristic_result:
            print(f"[AdaptiveElementMatcher] ✅ Heuristic found element: {heuristic_result['selector']}")
            return heuristic_result

        print(f"[AdaptiveElementMatcher] ❌ No element found for intent: '{intent}'")
        return None

    def _check_cached_selectors(self, url: str, intent: str) -> Optional[Dict[str, Any]]:
        """Check existing selector cache for the intent."""
        try:
            selector = self.selector_map.get_selector(url, "playwright_execute", intent)
            if selector:
                return {
                    "selector": selector,
                    "method": "cached",
                    "confidence": 0.9,
                    "element_info": {"type": "unknown", "text": "", "attributes": {}}
                }
        except Exception as e:
            print(f"[AdaptiveElementMatcher] Cache check failed: {e}")

        return None

    async def _ai_element_discovery(
        self,
        page: Page,
        intent: str,
        url: str,
        context_hints: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to analyze page and find element matching intent.

        Strategy:
        1. Get page context (title, visible text, interactive elements)
        2. Use LLM to identify likely selectors
        3. Test selectors and return best match
        """
        try:
            # Get page context
            page_context = await self._get_page_context(page, intent)

            # Build LLM prompt
            prompt = self._build_element_discovery_prompt(intent, page_context, context_hints)

            # Get LLM response (with caching)
            cache_key = f"{url}_{intent}_{hash(str(page_context))}"
            if cache_key in self._llm_cache:
                llm_response = self._llm_cache[cache_key]
            else:
                llm_response = await self._call_llm_for_element_discovery(prompt)
                self._llm_cache[cache_key] = llm_response

            # Parse LLM response
            selector_candidates = self._parse_llm_response(llm_response)

            # Test selectors and return best match
            best_match = await self._test_selectors(page, selector_candidates, intent)
            return best_match

        except Exception as e:
            print(f"[AdaptiveElementMatcher] AI discovery failed: {e}")
            return None

    async def _get_page_context(self, page: Page, intent: str) -> Dict[str, Any]:
        """Get comprehensive page context for LLM analysis."""
        try:
            # Get basic page info
            title = await page.title()
            url = page.url

            # Get visible text (first 1000 chars)
            visible_text = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    let text = '';
                    for (const el of elements) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.textContent) {
                            text += el.textContent.trim() + ' ';
                            if (text.length > 1000) break;
                        }
                    }
                    return text.substring(0, 1000);
                }
            """)

            # Get interactive elements
            interactive_elements = await page.evaluate("""
                () => {
                    const selectors = ['input', 'button', 'a', 'select', 'textarea', '[role="button"]', '[onclick]'];
                    const elements = [];

                    for (const selector of selectors) {
                        const found = document.querySelectorAll(selector);
                        for (const el of found) {
                            if (elements.length >= 20) break; // Limit to 20 elements

                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) { // Visible elements only
                                elements.push({
                                    tag: el.tagName.toLowerCase(),
                                    type: el.type || '',
                                    id: el.id || '',
                                    class: el.className || '',
                                    text: el.textContent?.substring(0, 50) || '',
                                    placeholder: el.placeholder || '',
                                    name: el.name || '',
                                    visible: true,
                                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                                });
                            }
                        }
                        if (elements.length >= 20) break;
                    }

                    return elements;
                }
            """)

            return {
                "title": title,
                "url": url,
                "visible_text": visible_text,
                "interactive_elements": interactive_elements,
                "intent": intent
            }

        except Exception as e:
            print(f"[AdaptiveElementMatcher] Failed to get page context: {e}")
            return {"title": "", "url": url, "visible_text": "", "interactive_elements": [], "intent": intent}

    def _build_element_discovery_prompt(self, intent: str, page_context: Dict[str, Any], context_hints: Optional[List[str]] = None) -> str:
        """Build LLM prompt for element discovery."""
        context_str = f"""
Page Title: {page_context['title']}
Page URL: {page_context['url']}
Visible Text Sample: {page_context['visible_text'][:500]}...

Interactive Elements:
{json.dumps(page_context['interactive_elements'][:10], indent=2)}

User Intent: Find element for "{intent}"
"""

        if context_hints:
            context_str += f"\nContext Hints: {', '.join(context_hints)}\n"

        prompt = f"""You are an expert at finding web elements based on user intent.

{context_str}

Based on the page content and user intent "{intent}", identify the most likely CSS selector for this element.

Common intent mappings:
- "search_input" → input[type="search"], input[placeholder*="search" i], input[name*="search"]
- "login_button" → button:contains("login"), input[type="submit"][value*="login"]
- "username" → input[name*="user"], input[id*="user"], input[placeholder*="email"]
- "password" → input[type="password"]
- "submit_button" → button[type="submit"], input[type="submit"]

Return a JSON object with:
{{
    "primary_selector": "CSS selector (most likely)",
    "fallback_selectors": ["selector1", "selector2"],
    "confidence": 0.0-1.0,
    "reasoning": "why this selector matches the intent"
}}

Return ONLY valid JSON:"""

        return prompt

    async def _call_llm_for_element_discovery(self, prompt: str) -> str:
        """Call LLM for element discovery."""
        try:
            from src.services.llm_service import LLMService
            from src.core.config import settings

            llm_service = LLMService(settings)
            model = llm_service.get_model()
            response = model.invoke(prompt)

            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            print(f"[AdaptiveElementMatcher] LLM call failed: {e}")
            return "{}"

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into selector candidates."""
        try:
            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                candidates = []

                # Primary selector
                if data.get('primary_selector'):
                    candidates.append({
                        "selector": data['primary_selector'],
                        "confidence": data.get('confidence', 0.8),
                        "reasoning": data.get('reasoning', '')
                    })

                # Fallback selectors
                for selector in data.get('fallback_selectors', []):
                    candidates.append({
                        "selector": selector,
                        "confidence": 0.6,
                        "reasoning": "LLM fallback"
                    })

                return candidates

        except Exception as e:
            print(f"[AdaptiveElementMatcher] Failed to parse LLM response: {e}")

        return []

    async def _test_selectors(
        self,
        page: Page,
        candidates: List[Dict[str, Any]],
        intent: str
    ) -> Optional[Dict[str, Any]]:
        """Test selectors and return the best working match."""
        for candidate in candidates:
            selector = candidate['selector']

            try:
                # Test if selector exists and is visible
                is_visible = await page.evaluate(f"""
                    () => {{
                        try {{
                            const el = document.querySelector('{selector}');
                            if (!el) return false;

                            const style = window.getComputedStyle(el);
                            const rect = el.getBoundingClientRect();

                            return style.display !== 'none' &&
                                   style.visibility !== 'hidden' &&
                                   rect.width > 0 &&
                                   rect.height > 0;
                        }} catch (e) {{
                            return false;
                        }}
                    }}
                """)

                if is_visible:
                    # Get element info
                    element_info = await page.evaluate(f"""
                        () => {{
                            try {{
                                const el = document.querySelector('{selector}');
                                if (!el) return {{}};

                                return {{
                                    type: el.type || '',
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id || '',
                                    class: el.className || '',
                                    text: el.textContent?.substring(0, 100) || '',
                                    placeholder: el.placeholder || '',
                                    name: el.name || ''
                                }};
                            }} catch (e) {{
                                return {{}};
                            }}
                        }}
                    """)

                    return {
                        "selector": selector,
                        "method": "ai_discovery",
                        "confidence": candidate['confidence'],
                        "element_info": element_info,
                        "reasoning": candidate.get('reasoning', '')
                    }

            except Exception as e:
                print(f"[AdaptiveElementMatcher] Selector test failed for '{selector}': {e}")
                continue

        return None

    async def _heuristic_fallback(self, page: Page, intent: str) -> Optional[Dict[str, Any]]:
        """Fallback to heuristic element detection."""
        try:
            # Use existing ElementParser for heuristics
            html = await page.content()
            elements = self.element_parser.parse_page(html)

            # Find matching element using heuristics
            match = self.element_parser.find_element(elements, intent)

            if match:
                return {
                    "selector": match['selector'],
                    "method": "heuristic",
                    "confidence": 0.5,
                    "element_info": match
                }

        except Exception as e:
            print(f"[AdaptiveElementMatcher] Heuristic fallback failed: {e}")

        return None

    def _cache_successful_match(self, url: str, intent: str, result: Dict[str, Any]):
        """Cache successful matches for future use."""
        try:
            domain = urlparse(url).netloc
            if domain.startswith('www.'):
                domain = domain[4:]

            # Cache in selector map
            self.selector_map.save_page_action_selector(domain, "/", intent, result['selector'])

            print(f"[AdaptiveElementMatcher] ✅ Cached selector for {intent}: {result['selector']}")

        except Exception as e:
            print(f"[AdaptiveElementMatcher] Failed to cache match: {e}")

    async def get_element_context(self, page: Page, selector: str) -> Dict[str, Any]:
        """Get detailed context about a found element."""
        try:
            context = await page.evaluate(f"""
                () => {{
                    try {{
                        const el = document.querySelector('{selector}');
                        if (!el) return {{}};

                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);

                        return {{
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            id: el.id || '',
                            class: el.className || '',
                            text: el.textContent?.substring(0, 200) || '',
                            placeholder: el.placeholder || '',
                            name: el.name || '',
                            value: el.value || '',
                            position: {{x: rect.x, y: rect.y, width: rect.width, height: rect.height}},
                            visible: style.display !== 'none' && style.visibility !== 'hidden',
                            enabled: !el.disabled,
                            attributes: Array.from(el.attributes).reduce((acc, attr) => {{
                                acc[attr.name] = attr.value;
                                return acc;
                            }}, {{}})
                        }};
                    }} catch (e) {{
                        return {{}};
                    }}
                }}
            """)

            return context

        except Exception as e:
            print(f"[AdaptiveElementMatcher] Failed to get element context: {e}")
            return {}
