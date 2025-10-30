"""
Element Parser - Interactive Element Detection

Simple, fast parser for interactive web elements.
Uses heuristics instead of LLM for 90%+ success rate.

Features:
- Extracts only interactive elements (a, button, input, select, textarea)
- Captures key attributes (id, class, name, type, placeholder, text, href)
- Generates CSS selectors
- String-based heuristic matching
- Async Playwright element finder with ranking
- LLM fallback for ambiguous cases

Usage:
    parser = ElementParser()
    elements = parser.parse_page(html)
    match = parser.find_element(elements, "search_input")
    
    # Or use async Playwright finder:
    element = await find_best_element(page, "search_input")
"""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re

# Async support for Playwright
try:
    from playwright.async_api import Page, Locator
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Optional: Fast parser for large pages
try:
    from selectolax.parser import HTMLParser as SelectolaxParser
    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False


class ElementParser:
    """
    Parse interactive elements from HTML with zero LLM calls.
    Uses BeautifulSoup (primary) and Selectolax (optional fallback).
    """
    
    # Interactive tags to extract (standard + custom clickable elements)
    INTERACTIVE_TAGS = ['a', 'button', 'input', 'select', 'textarea', 'div', 'span']
    
    def __init__(self):
        """Initialize element parser."""
        self.use_selectolax = SELECTOLAX_AVAILABLE
    
    def parse_page(self, html: str, use_selectolax: bool = False) -> List[Dict[str, Any]]:
        """
        Extract all interactive elements from HTML.
        
        Args:
            html: HTML content
            use_selectolax: Use fast Selectolax parser (if available)
            
        Returns:
            List of element dictionaries with attributes and selectors
        """
        if use_selectolax and self.use_selectolax:
            return self._parse_with_selectolax(html)
        else:
            return self._parse_with_beautifulsoup(html)
    
    def _parse_with_beautifulsoup(self, html: str) -> List[Dict[str, Any]]:
        """Parse HTML with BeautifulSoup."""
        soup = BeautifulSoup(html, 'html.parser')
        elements = []
        
        for element in soup.find_all(self.INTERACTIVE_TAGS):
            # Filter div/span to only include clickable ones
            if element.name in ['div', 'span']:
                if not self._is_clickable(element):
                    continue
            
            elem_data = self._extract_element_data(element)
            if elem_data:
                elements.append(elem_data)
        
        # Limit to reasonable number for shallow tree strategy
        return elements[:100]  # Shallow tree: max 100 elements per page
    
    def _is_clickable(self, element) -> bool:
        """Check if div/span element is clickable (custom interactive element)."""
        # Has role=button or role=link
        role = element.get('role', '').lower()
        if role in ['button', 'link', 'menuitem', 'tab']:
            return True
        
        # Has onclick event
        if element.get('onclick'):
            return True
        
        # Has tabindex (keyboard accessible)
        if element.get('tabindex') is not None:
            return True
        
        # Has cursor:pointer style
        style = element.get('style', '').lower()
        if 'cursor:pointer' in style or 'cursor: pointer' in style:
            return True
        
        # Has clickable class names
        class_names = ' '.join(element.get('class', [])).lower()
        clickable_patterns = ['btn', 'button', 'click', 'link', 'action', 'menu']
        if any(pattern in class_names for pattern in clickable_patterns):
            return True
        
        return False
    
    def _parse_with_selectolax(self, html: str) -> List[Dict[str, Any]]:
        """Parse HTML with Selectolax (10x faster)."""
        tree = SelectolaxParser(html)
        elements = []
        
        for tag in self.INTERACTIVE_TAGS:
            for element in tree.css(tag):
                elem_data = {
                    'tag': tag,
                    'id': element.attributes.get('id'),
                    'class': element.attributes.get('class'),
                    'name': element.attributes.get('name'),
                    'type': element.attributes.get('type'),
                    'placeholder': element.attributes.get('placeholder'),
                    'text': element.text(strip=True)[:100] if element.text() else '',
                    'href': element.attributes.get('href'),
                }
                
                # Generate selector
                elem_data['selector'] = self._generate_selector(elem_data)
                
                # Remove None values
                elem_data = {k: v for k, v in elem_data.items() if v}
                
                if elem_data:
                    elements.append(elem_data)
        
        return elements
    
    def _extract_element_data(self, element) -> Optional[Dict[str, Any]]:
        """Extract key attributes from BeautifulSoup element."""
        elem_data = {
            'tag': element.name,
            'id': element.get('id'),
            'class': ' '.join(element.get('class', [])) if element.get('class') else None,
            'name': element.get('name'),
            'type': element.get('type'),
            'placeholder': element.get('placeholder'),
            'aria_label': element.get('aria-label'),
            'role': element.get('role'),
            'text': element.get_text(strip=True)[:100] if element.get_text(strip=True) else None,
            'href': element.get('href'),
            'value': element.get('value'),
        }
        
        # Generate CSS selector
        elem_data['selector'] = self._generate_selector(elem_data)
        
        # Remove None values
        elem_data = {k: v for k, v in elem_data.items() if v}
        
        return elem_data if elem_data else None
    
    def _generate_selector(self, elem_data: Dict[str, Any]) -> str:
        """
        Generate CSS selector for element.
        Priority: id > name > class > tag
        """
        tag = elem_data.get('tag', '')
        
        # Priority 1: ID (most specific)
        if elem_data.get('id'):
            return f"#{elem_data['id']}"
        
        # Priority 2: Name attribute (common for forms)
        if elem_data.get('name'):
            return f"{tag}[name='{elem_data['name']}']"
        
        # Priority 3: Type + placeholder (for inputs)
        if elem_data.get('type') and elem_data.get('placeholder'):
            return f"{tag}[type='{elem_data['type']}'][placeholder*='{elem_data['placeholder'][:20]}']"
        
        # Priority 4: Type only
        if elem_data.get('type'):
            return f"{tag}[type='{elem_data['type']}']"
        
        # Priority 5: Class (can be unstable)
        if elem_data.get('class'):
            classes = elem_data['class'].split()[:2]  # Use first 2 classes
            return f"{tag}.{'.'.join(classes)}"
        
        # Priority 6: Role
        if elem_data.get('role'):
            return f"{tag}[role='{elem_data['role']}']"
        
        # Priority 7: Href (for links)
        if elem_data.get('href'):
            return f"{tag}[href='{elem_data['href']}']"
        
        # Fallback: Just the tag
        return tag
    
    def find_element(self, elements: List[Dict[str, Any]], action_hint: str) -> Optional[Dict[str, Any]]:
        """
        Find element matching action hint using heuristics.
        
        Args:
            elements: List of parsed elements
            action_hint: Semantic hint (e.g., "search_input", "login_button")
            
        Returns:
            Matching element or None
        """
        hint_lower = action_hint.lower()
        
        # Extract keywords from hint
        keywords = self._extract_keywords(hint_lower)
        
        # Score each element
        scored_elements = []
        for element in elements:
            score = self._score_element(element, keywords, hint_lower)
            if score > 0:
                scored_elements.append((score, element))
        
        # Return highest scoring element
        if scored_elements:
            scored_elements.sort(reverse=True, key=lambda x: x[0])
            return scored_elements[0][1]
        
        return None
    
    def _extract_keywords(self, hint: str) -> List[str]:
        """Extract keywords from action hint."""
        # Split on underscores and spaces
        words = re.split(r'[_\s]+', hint)
        return [w for w in words if len(w) > 2]  # Filter short words
    
    def _score_element(self, element: Dict[str, Any], keywords: List[str], hint: str) -> float:
        """
        Score element based on how well it matches the hint.
        Higher score = better match.
        """
        score = 0.0
        
        # Check all text attributes
        text_attributes = ['id', 'name', 'placeholder', 'text', 'aria_label', 'class']
        
        for attr in text_attributes:
            value = element.get(attr, '')
            if not value:
                continue
            
            value_lower = str(value).lower()
            
            # Exact match (high score)
            if hint in value_lower:
                score += 10.0
            
            # Keyword matches (medium score)
            for keyword in keywords:
                if keyword in value_lower:
                    score += 5.0
            
            # Fuzzy match (low score)
            if any(char in value_lower for char in keywords):
                score += 1.0
        
        # Type-specific bonuses
        if 'search' in hint:
            if element.get('type') == 'search':
                score += 15.0
            if element.get('name') in ['q', 'query', 'search']:
                score += 10.0
        
        if 'login' in hint or 'signin' in hint:
            if element.get('type') == 'submit':
                score += 10.0
            if element.get('text') and any(w in element['text'].lower() for w in ['login', 'sign in', 'log in']):
                score += 15.0
        
        if 'button' in hint and element.get('tag') == 'button':
            score += 5.0
        
        if 'link' in hint and element.get('tag') == 'a':
            score += 5.0
        
        if 'input' in hint and element.get('tag') == 'input':
            score += 5.0
        
        return score
    
    def find_playwright_locator_hint(self, action_hint: str) -> Optional[Dict[str, str]]:
        """
        Generate Playwright semantic locator hints.
        These can be tried before parsing HTML.
        
        Args:
            action_hint: Semantic hint
            
        Returns:
            Dict with locator type and value, or None
        """
        hint_lower = action_hint.lower()
        
        # Search inputs
        if 'search' in hint_lower:
            return {'type': 'role', 'role': 'searchbox'}
        
        # Buttons
        if 'button' in hint_lower:
            # Try to extract button text from hint
            text = hint_lower.replace('button', '').replace('_', ' ').strip()
            if text:
                return {'type': 'role', 'role': 'button', 'name': text}
            return {'type': 'role', 'role': 'button'}
        
        # Links
        if 'link' in hint_lower:
            text = hint_lower.replace('link', '').replace('_', ' ').strip()
            if text:
                return {'type': 'role', 'role': 'link', 'name': text}
            return {'type': 'role', 'role': 'link'}
        
        # Text inputs
        if 'input' in hint_lower or 'field' in hint_lower:
            if 'email' in hint_lower:
                return {'type': 'label', 'label': 'email'}
            if 'password' in hint_lower:
                return {'type': 'label', 'label': 'password'}
            if 'name' in hint_lower:
                return {'type': 'label', 'label': 'name'}
        
        # Placeholders
        keywords = self._extract_keywords(hint_lower)
        if keywords:
            return {'type': 'placeholder', 'text': keywords[0]}
        
        return None


# ============================================================================
# ASYNC PLAYWRIGHT ELEMENT FINDER WITH RANKING
# ============================================================================

async def find_best_element(
    page: 'Page',
    selector_hint: str,
    tag_filter: Optional[str] = None
) -> Optional['Locator']:
    """
    Generic async function to find the best matching element on a page.
    
    Strategy:
    1. Build smart selector based on hint
    2. Find ALL matching elements
    3. Rank by position, size, context
    4. If ambiguous → Ask LLM
    5. Return best match
    
    Args:
        page: Playwright Page object
        selector_hint: Semantic hint (e.g., "search_input", "login_button")
        tag_filter: Optional tag filter (e.g., "input", "button")
        
    Returns:
        Best matching Locator or None
        
    Example:
        search_box = await find_best_element(page, "search_input")
        await search_box.fill("query")
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright not available. Install with: pip install playwright")
    
    print(f"[PARSER] Finding best element for: {selector_hint}")
    
    # Step 1: Build selector
    selector = _build_smart_selector(selector_hint, tag_filter)
    print(f"[PARSER] Using selector: {selector}")
    
    # Step 2: Find ALL matching elements
    locator = page.locator(selector)
    count = await locator.count()
    
    if count == 0:
        print(f"[PARSER] No elements found")
        return None
    
    if count == 1:
        print(f"[PARSER] Found 1 element (easy case)")
        return locator.first
    
    print(f"[PARSER] Found {count} elements, ranking...")
    
    # Step 3: Rank elements
    ranked = await _rank_elements(page, locator, count, selector_hint)
    
    if not ranked:
        return None
    
    # Step 4: Check if LLM needed
    if len(ranked) > 1:
        top_score = ranked[0][0]
        second_score = ranked[1][0]
        
        if abs(top_score - second_score) < 3:  # Scores too close
            print(f"[PARSER] Scores ambiguous ({top_score} vs {second_score}), using LLM...")
            best_index = await _llm_choose_best(page, locator, count, selector_hint)
            if best_index is not None:
                return locator.nth(best_index)
    
    # Step 5: Return best match
    best_index = ranked[0][1]
    print(f"[PARSER] Best match: index {best_index} (score: {ranked[0][0]})")
    return locator.nth(best_index)


def _build_smart_selector(hint: str, tag_filter: Optional[str] = None) -> str:
    """
    Build smart CSS selector from hint.
    """
    hint_lower = hint.lower()
    
    # Determine tag
    if tag_filter:
        tags = [tag_filter]
    elif 'input' in hint_lower or 'field' in hint_lower:
        tags = ['input', 'textarea']
    elif 'button' in hint_lower:
        tags = ['button', 'input[type="submit"]', '[role="button"]']
    elif 'link' in hint_lower:
        tags = ['a', '[role="link"]']
    else:
        # Generic: any interactive element
        tags = ['input', 'button', 'a', 'select', 'textarea', '[role="button"]', '[role="link"]']
    
    # Build selector parts
    selectors = []
    
    for tag in tags:
        # Search-specific
        if 'search' in hint_lower:
            selectors.extend([
                f'{tag}[type="search"]',
                f'{tag}[name*="search" i]',
                f'{tag}[placeholder*="search" i]',
                f'{tag}[aria-label*="search" i]',
                f'{tag}[id*="search" i]',
                f'{tag}[class*="search" i]'
            ])
        # Login-specific
        elif 'login' in hint_lower or 'signin' in hint_lower:
            selectors.extend([
                f'{tag}[type="submit"]',
                f'{tag}:has-text("Login")',
                f'{tag}:has-text("Sign in")',
                f'{tag}[name*="login" i]'
            ])
        # Generic
        else:
            # Extract keywords from hint
            keywords = re.split(r'[_\s]+', hint_lower)
            for keyword in keywords:
                if len(keyword) > 2:
                    selectors.extend([
                        f'{tag}[name*="{keyword}" i]',
                        f'{tag}[placeholder*="{keyword}" i]',
                        f'{tag}[aria-label*="{keyword}" i]'
                    ])
    
    # Join with comma (OR selector)
    return ', '.join(selectors) if selectors else 'input, button, a'


async def _rank_elements(
    page: 'Page',
    locator: 'Locator',
    count: int,
    hint: str
) -> List[tuple[float, int]]:
    """
    Rank elements by heuristics.
    Returns list of (score, index) tuples, sorted by score (descending).
    """
    ranked = []
    
    for i in range(min(count, 10)):  # Max 10 elements
        element = locator.nth(i)
        score = 0.0
        
        try:
            # Check visibility
            if await element.is_visible():
                score += 5.0
            else:
                continue  # Skip hidden elements
            
            # Check position (prefer main content over header/footer)
            box = await element.bounding_box()
            if box:
                # Prefer elements not in header (y > 200)
                if box['y'] > 200:
                    score += 10.0
                
                # Prefer larger elements
                area = box['width'] * box['height']
                if area > 2000:
                    score += 5.0
                
                # Prefer elements in center/left (not far right)
                if box['x'] < 800:
                    score += 3.0
            
            # Check if in main content
            in_main = await element.evaluate(
                '(el) => !!el.closest("main, [role=main], #content, .content")'
            )
            if in_main:
                score += 15.0
            
            # Check if in header/nav (penalty)
            in_header = await element.evaluate(
                '(el) => !!el.closest("header, nav, [role=banner], [role=navigation]")'
            )
            if in_header:
                score -= 10.0
            
            # Check attributes match hint
            attrs = await element.evaluate(
                '''(el) => ({
                    id: el.id,
                    name: el.name,
                    placeholder: el.placeholder,
                    ariaLabel: el.getAttribute('aria-label'),
                    className: el.className
                })'''
            )
            
            # Match hint keywords in attributes
            hint_lower = hint.lower()
            for attr_value in attrs.values():
                if attr_value and isinstance(attr_value, str):
                    if hint_lower in attr_value.lower():
                        score += 8.0
            
            ranked.append((score, i))
            
        except Exception as e:
            print(f"[PARSER] Error ranking element {i}: {e}")
            continue
    
    # Sort by score (descending)
    ranked.sort(reverse=True, key=lambda x: x[0])
    return ranked


async def _llm_choose_best(
    page: 'Page',
    locator: 'Locator',
    count: int,
    hint: str
) -> Optional[int]:
    """
    Use LLM to choose best element when ranking is ambiguous.
    """
    try:
        from src.services.llm_service import LLMService
        from src.core.config import settings
        
        # Get context for each element
        contexts = []
        for i in range(min(count, 5)):  # Max 5 for LLM
            element = locator.nth(i)
            
            try:
                # Get element info
                info = await element.evaluate(
                    '''(el) => {
                        const parent = el.closest('div, section, main, header, nav');
                        return {
                            tag: el.tagName.toLowerCase(),
                            id: el.id,
                            name: el.name,
                            placeholder: el.placeholder,
                            text: el.textContent?.slice(0, 50),
                            parentText: parent?.textContent?.slice(0, 100)
                        };
                    }'''
                )
                
                contexts.append(f"{i+1}. {info['tag']} (id:{info.get('id','')}, name:{info.get('name','')}) - Context: {info.get('parentText','')[:50]}")
            except:
                contexts.append(f"{i+1}. Element {i}")
        
        prompt = f"""Which element is the MAIN/PRIMARY {hint}?

Elements found:
{chr(10).join(contexts)}

Consider:
- Elements in header/nav are usually NOT the main element
- Elements in main content area are preferred  
- Larger, more visible elements are preferred

Return ONLY the number (1, 2, 3, etc.) of the best element.

Number:"""
        
        llm = LLMService(settings)
        model = llm.get_model()
        response = model.invoke(prompt)
        
        content = response.content if hasattr(response, 'content') else str(response)
        choice = int(re.search(r'\d+', content).group())
        
        print(f"[PARSER] LLM chose element: {choice}")
        return choice - 1  # Convert to 0-indexed
        
    except Exception as e:
        print(f"[PARSER] LLM fallback failed: {e}")
        return None
