"""
Page Intelligence Scanner - Identify Interactive Elements

Scans web pages after navigation and builds a semantic registry of
interactive elements (inputs, buttons, links) with clear labels.

This registry enables:
1. Reliable element identification
2. Semantic element references ("search_input" vs "#twotabsearchtextbox")
3. Smart fallback strategies (press Enter if button not clickable)
4. Plan enforcement with correct selectors
"""

from typing import Dict, Any, List, Optional
import re


class PageIntelligenceScanner:
    """
    Scans page and identifies interactive elements with semantic labels.
    """

    # Common purposes for inputs (heuristic matching)
    INPUT_PURPOSES = {
        'search': ['search', 'query', 'q', 'find', 'buscar'],
        'email': ['email', 'e-mail', 'mail'],
        'password': ['password', 'pass', 'pwd'],
        'username': ['username', 'user', 'login'],
        'phone': ['phone', 'tel', 'mobile'],
        'name': ['name', 'firstname', 'lastname'],
        'address': ['address', 'street', 'city', 'zip'],
        'date': ['date', 'calendar', 'day', 'month', 'year'],
        'quantity': ['quantity', 'qty', 'amount'],
        'price': ['price', 'cost', 'amount']
    }

    # Common purposes for buttons
    BUTTON_PURPOSES = {
        'search': ['search', 'find', 'go'],
        'submit': ['submit', 'send', 'confirm', 'continue'],
        'login': ['login', 'sign in', 'log in'],
        'signup': ['sign up', 'register', 'join'],
        'buy': ['buy', 'purchase', 'add to cart', 'checkout'],
        'close': ['close', 'dismiss', 'cancel', 'x'],
        'next': ['next', 'continue', 'forward'],
        'back': ['back', 'previous', 'return']
    }

    def infer_input_purpose(self, attrs: Dict[str, str]) -> str:
        """
        Infer input purpose from attributes using heuristics.

        Args:
            attrs: Element attributes (id, name, type, placeholder, aria-label, etc.)

        Returns:
            Purpose string (e.g., "search", "email", "password")
        """
        # Combine all text attributes for matching
        text_to_match = ' '.join([
            attrs.get('id', ''),
            attrs.get('name', ''),
            attrs.get('placeholder', ''),
            attrs.get('aria-label', ''),
            attrs.get('title', '')
        ]).lower()

        # Check type attribute first
        input_type = attrs.get('type', 'text').lower()
        if input_type in ['email', 'password', 'tel', 'search', 'date']:
            return input_type

        # Match against purpose patterns
        for purpose, keywords in self.INPUT_PURPOSES.items():
            if any(keyword in text_to_match for keyword in keywords):
                return purpose

        return 'text'  # Default

    def infer_button_purpose(self, attrs: Dict[str, str], text: str) -> str:
        """
        Infer button purpose from attributes and text.

        Args:
            attrs: Element attributes
            text: Button text content

        Returns:
            Purpose string (e.g., "search", "submit", "login")
        """
        # Combine all text for matching
        text_to_match = ' '.join([
            text,
            attrs.get('id', ''),
            attrs.get('class', ''),
            attrs.get('aria-label', ''),
            attrs.get('title', '')
        ]).lower()

        # Check type attribute
        button_type = attrs.get('type', '').lower()
        if button_type == 'submit':
            # Refine submit buttons based on context
            for purpose, keywords in self.BUTTON_PURPOSES.items():
                if any(keyword in text_to_match for keyword in keywords):
                    return purpose
            return 'submit'

        # Match against purpose patterns
        for purpose, keywords in self.BUTTON_PURPOSES.items():
            if any(keyword in text_to_match for keyword in keywords):
                return purpose

        return 'button'  # Default

    def generate_semantic_name(self, purpose: str, element_type: str, index: int = 0) -> str:
        """
        Generate semantic name for element.

        Args:
            purpose: Element purpose (e.g., "search")
            element_type: Element type ("input" or "button")
            index: Index if multiple elements with same purpose

        Returns:
            Semantic name (e.g., "search_input", "search_input_2")
        """
        base_name = f"{purpose}_{element_type}"
        if index > 0:
            return f"{base_name}_{index + 1}"
        return base_name

    async def scan_page(self, page) -> Dict[str, Any]:
        """
        Scan page and build element registry.

        Args:
            page: Playwright page object

        Returns:
            Element registry with semantic labels
        """
        registry = {
            "inputs": {},
            "buttons": {},
            "selects": {},
            "url": page.url,
            "title": await page.title()
        }

        # Track counts for semantic naming
        input_counts = {}
        button_counts = {}

        try:
            # Scan inputs
            inputs = await page.query_selector_all("input:not([type='hidden']), textarea")

            for input_el in inputs:
                try:
                    # Get attributes
                    attrs = await input_el.evaluate("""
                        el => {
                            const attrs = {};
                            ['id', 'name', 'type', 'placeholder', 'aria-label', 'title', 'class', 'value'].forEach(attr => {
                                const val = el.getAttribute(attr);
                                if (val) attrs[attr] = val;
                            });
                            return attrs;
                        }
                    """)

                    # Check visibility
                    is_visible = await input_el.is_visible()

                    if not is_visible:
                        continue  # Skip hidden inputs

                    # Get unique selector
                    selector = await self._get_unique_selector(input_el, attrs)

                    # Infer purpose
                    purpose = self.infer_input_purpose(attrs)

                    # Generate semantic name
                    count = input_counts.get(purpose, 0)
                    semantic_name = self.generate_semantic_name(purpose, "input", count)
                    input_counts[purpose] = count + 1

                    # Add to registry
                    registry["inputs"][semantic_name] = {
                        "selector": selector,
                        "type": attrs.get("type", "text"),
                        "purpose": purpose,
                        "label": attrs.get("aria-label") or attrs.get("placeholder") or attrs.get("name"),
                        "visible": is_visible,
                        "attributes": attrs
                    }

                except Exception as e:
                    print(f"[PAGE_INTEL] Error scanning input: {e}")
                    continue

            # Scan buttons
            buttons = await page.query_selector_all("button, input[type='submit'], input[type='button'], a[role='button']")

            for button_el in buttons:
                try:
                    # Get attributes and text
                    data = await button_el.evaluate("""
                        el => {
                            const attrs = {};
                            ['id', 'name', 'type', 'aria-label', 'title', 'class', 'role'].forEach(attr => {
                                const val = el.getAttribute(attr);
                                if (val) attrs[attr] = val;
                            });
                            return {
                                attrs: attrs,
                                text: el.innerText || el.textContent || '',
                                visible: el.offsetWidth > 0 && el.offsetHeight > 0
                            };
                        }
                    """)

                    attrs = data['attrs']
                    text = data['text'].strip()
                    is_visible = data['visible']

                    if not is_visible:
                        continue  # Skip hidden buttons

                    # Check if in viewport
                    in_viewport = await self._is_in_viewport(button_el)

                    # Get unique selector
                    selector = await self._get_unique_selector(button_el, attrs)

                    # Infer purpose
                    purpose = self.infer_button_purpose(attrs, text)

                    # Generate semantic name
                    count = button_counts.get(purpose, 0)
                    semantic_name = self.generate_semantic_name(purpose, "button", count)
                    button_counts[purpose] = count + 1

                    # Add to registry
                    registry["buttons"][semantic_name] = {
                        "selector": selector,
                        "text": text,
                        "purpose": purpose,
                        "visible": is_visible,
                        "in_viewport": in_viewport,
                        "clickable": in_viewport,  # If in viewport, assume clickable
                        "attributes": attrs
                    }

                except Exception as e:
                    print(f"[PAGE_INTEL] Error scanning button: {e}")
                    continue

            # Scan select dropdowns
            selects = await page.query_selector_all("select")

            for select_el in selects:
                try:
                    attrs = await select_el.evaluate("""
                        el => {
                            const attrs = {};
                            ['id', 'name', 'aria-label', 'title', 'class'].forEach(attr => {
                                const val = el.getAttribute(attr);
                                if (val) attrs[attr] = val;
                            });
                            return attrs;
                        }
                    """)

                    is_visible = await select_el.is_visible()

                    if not is_visible:
                        continue

                    selector = await self._get_unique_selector(select_el, attrs)

                    # Infer purpose from name/label
                    purpose = self._infer_select_purpose(attrs)

                    registry["selects"][purpose] = {
                        "selector": selector,
                        "purpose": purpose,
                        "visible": is_visible,
                        "attributes": attrs
                    }

                except Exception as e:
                    print(f"[PAGE_INTEL] Error scanning select: {e}")
                    continue

            print(f"[PAGE_INTEL] ✅ Scanned page: {len(registry['inputs'])} inputs, {len(registry['buttons'])} buttons, {len(registry['selects'])} selects")

            return registry

        except Exception as e:
            print(f"[PAGE_INTEL] ❌ Scan failed: {e}")
            return registry

    def _infer_select_purpose(self, attrs: Dict[str, str]) -> str:
        """Infer select dropdown purpose."""
        text_to_match = ' '.join([
            attrs.get('id', ''),
            attrs.get('name', ''),
            attrs.get('aria-label', ''),
        ]).lower()

        if 'date' in text_to_match or 'day' in text_to_match or 'month' in text_to_match:
            return 'date_select'
        elif 'country' in text_to_match or 'location' in text_to_match:
            return 'location_select'
        elif 'category' in text_to_match or 'type' in text_to_match:
            return 'category_select'

        return 'select'

    async def _get_unique_selector(self, element, attrs: Dict[str, str]) -> str:
        """
        Generate unique CSS selector for element.

        Priority:
        1. ID
        2. Name attribute
        3. Aria-label + tag
        4. Class + tag
        """
        # Try ID first
        if 'id' in attrs and attrs['id']:
            return f"#{attrs['id']}"

        # Try name
        if 'name' in attrs and attrs['name']:
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            return f"{tag}[name='{attrs['name']}']"

        # Try aria-label
        if 'aria-label' in attrs and attrs['aria-label']:
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            return f"{tag}[aria-label='{attrs['aria-label']}']"

        # Fallback: generate from class
        if 'class' in attrs and attrs['class']:
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            classes = attrs['class'].split()
            if classes:
                return f"{tag}.{classes[0]}"

        # Last resort: nth-of-type
        tag = await element.evaluate("el => el.tagName.toLowerCase()")
        return tag

    async def _is_in_viewport(self, element) -> bool:
        """Check if element is in viewport."""
        try:
            return await element.evaluate("""
                el => {
                    const rect = el.getBoundingClientRect();
                    return (
                        rect.top >= 0 &&
                        rect.left >= 0 &&
                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                    );
                }
            """)
        except:
            return False


# Singleton instance
_scanner = None

def get_page_intelligence_scanner() -> PageIntelligenceScanner:
    """Get singleton scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = PageIntelligenceScanner()
    return _scanner
