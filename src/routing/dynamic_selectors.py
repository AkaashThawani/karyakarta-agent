"""
Dynamic Selector & Method Generation

Generates fallback selectors and chooses extraction methods dynamically
based on Site Intelligence, LLM inference, and element analysis.
"""

from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import json


class DynamicSelectorGenerator:
    """Generate fallback selectors dynamically using multiple strategies."""
    
    def __init__(self):
        self.cache = {}
    
    async def generate_fallback_selectors(
        self,
        url: str,
        target_content: str,
        llm_service,
        max_selectors: int = 5
    ) -> List[str]:
        """
        Generate multiple fallback selectors dynamically.
        
        Uses:
        1. Site Intelligence learned elements
        2. LLM to generate variations
        3. Common patterns for the target
        
        Args:
            url: Page URL
            target_content: What to find (e.g., "specifications", "price", "title")
            llm_service: LLM service for generation
            max_selectors: Maximum number of selectors to generate
            
        Returns:
            List of CSS selectors to try
        """
        from src.tools.site_intelligence import SiteIntelligenceTool
        
        selectors = []
        
        # Parse domain
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # 1. Get selectors from Site Intelligence cache
        intelligence = SiteIntelligenceTool()
        schema = intelligence.load_schema(domain)
        
        if schema and 'elements' in schema:
            # Find elements that match target content
            for name, element in schema['elements'].items():
                if self._matches_target(name, element.get('purpose', ''), target_content):
                    selector = element.get('selector')
                    if selector and selector not in selectors:
                        selectors.append(selector)
                        print(f"[DYNAMIC] Added selector from Site Intelligence: {selector}")
        
        # 2. Use LLM to generate selector variations
        if len(selectors) < max_selectors:
            llm_selectors = await self._generate_with_llm(
                url, target_content, llm_service, max_selectors - len(selectors)
            )
            for sel in llm_selectors:
                if sel not in selectors:
                    selectors.append(sel)
        
        # 3. Add generic patterns based on target
        if len(selectors) < max_selectors:
            generic = self._generate_generic_patterns(target_content)
            for sel in generic:
                if sel not in selectors and len(selectors) < max_selectors:
                    selectors.append(sel)
        
        print(f"[DYNAMIC] Generated {len(selectors)} fallback selectors for '{target_content}'")
        return selectors[:max_selectors]
    
    def _matches_target(self, name: str, purpose: str, target: str) -> bool:
        """Check if element name/purpose matches target."""
        target_lower = target.lower()
        name_lower = name.lower()
        purpose_lower = purpose.lower()
        
        # Direct match
        if target_lower in name_lower or target_lower in purpose_lower:
            return True
        
        # Keyword matching
        target_keywords = target_lower.split('_')
        for keyword in target_keywords:
            if keyword in name_lower or keyword in purpose_lower:
                return True
        
        return False
    
    async def _generate_with_llm(
        self,
        url: str,
        target_content: str,
        llm_service,
        count: int
    ) -> List[str]:
        """Use LLM to generate selector variations."""
        prompt = f"""Generate {count} CSS selectors to find "{target_content}" content on {url}.

Consider:
- Common patterns for this type of content
- Variations in class/id naming conventions
- Semantic HTML elements
- Data attributes
- Amazon/e-commerce specific patterns if applicable

Return ONLY a JSON array of selectors (no explanation):
["selector1", "selector2", "selector3"]

Be creative and consider multiple approaches!"""

        try:
            model = llm_service.get_model()
            response = await model.ainvoke(prompt)
            content = response.content.strip()
            
            # Try to parse JSON
            import re
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                selectors = json.loads(json_match.group(0))
                if isinstance(selectors, list):
                    print(f"[DYNAMIC] LLM generated {len(selectors)} selectors")
                    return [str(s) for s in selectors if s]
        except Exception as e:
            print(f"[DYNAMIC] LLM selector generation failed: {e}")
        
        return []
    
    def _generate_generic_patterns(self, target: str) -> List[str]:
        """Generate generic CSS patterns based on target."""
        target_clean = target.lower().replace('_', '-').replace(' ', '-')
        
        patterns = [
            f"div[class*='{target_clean}']",
            f"section[class*='{target_clean}']",
            f"div[id*='{target_clean}']",
            f"div.{target_clean}",
            f"#{target_clean}",
            f"[data-{target_clean}]",
            f"div[data-testid*='{target_clean}']"
        ]
        
        # Add specific patterns for common targets
        if 'spec' in target.lower():
            patterns.extend([
                'div#feature-bullets',
                'div#detailBullets_feature_div',
                'table#productDetails_techSpec_section_1',
                'table#productDetails_techSpec_section_2',
                'div.a-section.a-spacing-medium'
            ])
        elif 'price' in target.lower():
            patterns.extend([
                'span.a-price',
                'span[class*="price"]',
                'div[data-price]',
                '[class*="Price"]'
            ])
        elif 'title' in target.lower():
            patterns.extend([
                'h1#title',
                'h1.product-title',
                'span#productTitle',
                'h1[class*="title"]'
            ])
        
        return patterns


class DynamicMethodSelector:
    """Select extraction method based on element structure."""
    
    async def select_extraction_method(
        self,
        page,
        selector: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically choose best extraction method.
        
        Args:
            page: Playwright page
            selector: CSS selector
            content_type: Optional hint ('text', 'table', 'list', 'structured')
            
        Returns:
            Method configuration dict
        """
        # Analyze element structure
        element_info = await page.evaluate(f"""
            (selector) => {{
                const el = document.querySelector(selector);
                if (!el) return null;
                
                return {{
                    tagName: el.tagName.toLowerCase(),
                    hasTable: el.querySelector('table') !== null,
                    hasList: el.querySelector('ul, ol') !== null,
                    hasDefinitionList: el.querySelector('dl') !== null,
                    childCount: el.children.length,
                    textLength: el.textContent?.trim().length || 0,
                    hasStructuredData: el.querySelector('[itemscope]') !== null
                }};
            }}
        """, selector)
        
        if not element_info:
            # Fallback to simple text extraction
            return {
                'method': 'inner_text',
                'selector': selector,
                'args': {}
            }
        
        # Choose method based on structure
        if element_info.get('hasTable'):
            # Extract table data
            return {
                'method': 'evaluate',
                'args': {
                    'expression': f"""
                        Array.from(document.querySelectorAll('{selector} table tr'))
                            .map(row => Array.from(row.cells)
                                .map(cell => cell.textContent.trim())
                                .join(': '))
                            .join('\\n')
                    """
                }
            }
        elif element_info.get('hasList'):
            # Extract list items
            return {
                'method': 'evaluate',
                'args': {
                    'expression': f"""
                        Array.from(document.querySelectorAll('{selector} li'))
                            .map(li => li.textContent.trim())
                            .join('\\n')
                    """
                }
            }
        elif element_info.get('hasDefinitionList'):
            # Extract definition list (dl/dt/dd)
            return {
                'method': 'evaluate',
                'args': {
                    'expression': f"""
                        Array.from(document.querySelectorAll('{selector} dt'))
                            .map((dt, i) => {{
                                const dd = document.querySelectorAll('{selector} dd')[i];
                                return dt.textContent.trim() + ': ' + (dd ? dd.textContent.trim() : '');
                            }})
                            .join('\\n')
                    """
                }
            }
        elif element_info.get('childCount', 0) > 10:
            # Complex structure - try to get all text
            return {
                'method': 'evaluate',
                'args': {
                    'expression': f"""
                        document.querySelector('{selector}').textContent.trim()
                    """
                }
            }
        else:
            # Simple text extraction
            return {
                'method': 'inner_text',
                'selector': selector,
                'args': {}
            }
    
    def calculate_confidence(self, result: Any, target: str) -> float:
        """Calculate confidence score for extraction result."""
        if not result:
            return 0.0
        
        result_str = str(result).lower()
        target_lower = target.lower()
        
        # Check if target keywords are in result
        score = 0.0
        keywords = target_lower.split('_')
        
        for keyword in keywords:
            if keyword in result_str:
                score += 0.3
        
        # Check result length (longer is usually better for specs)
        if len(result_str) > 100:
            score += 0.3
        elif len(result_str) > 50:
            score += 0.2
        
        # Check for structured data patterns
        if ':' in result_str or '|' in result_str:
            score += 0.2
        
        return min(score, 1.0)


async def extract_with_fallbacks(
    page,
    url: str,
    target: str,
    llm_service
) -> Optional[Dict[str, Any]]:
    """
    Try multiple selectors and methods adaptively.
    
    Args:
        page: Playwright page
        url: Current URL
        target: What to extract
        llm_service: LLM service
        
    Returns:
        Best extraction result or None
    """
    generator = DynamicSelectorGenerator()
    method_selector = DynamicMethodSelector()
    
    # Generate fallback selectors
    selectors = await generator.generate_fallback_selectors(url, target, llm_service)
    
    if not selectors:
        print(f"[DYNAMIC] No selectors generated for '{target}'")
        return None
    
    results = []
    
    for i, selector in enumerate(selectors):
        try:
            # Choose best method for this selector
            method_config = await method_selector.select_extraction_method(page, selector, target)
            
            print(f"[DYNAMIC] Trying selector {i+1}/{len(selectors)}: {selector}")
            print(f"[DYNAMIC] Using method: {method_config['method']}")
            
            # Try extraction
            if method_config['method'] == 'evaluate':
                result = await page.evaluate(method_config['args']['expression'])
            elif method_config['method'] == 'inner_html':
                result = await page.inner_html(selector)
            else:  # inner_text
                result = await page.inner_text(selector)
            
            if result and len(str(result).strip()) > 0:
                confidence = method_selector.calculate_confidence(result, target)
                results.append({
                    'selector': selector,
                    'method': method_config['method'],
                    'data': result,
                    'confidence': confidence
                })
                print(f"[DYNAMIC] ✅ Extracted data (confidence: {confidence:.2f})")
            
        except Exception as e:
            print(f"[DYNAMIC] ❌ Selector failed: {e}")
            continue
    
    # Return best result
    if results:
        best = max(results, key=lambda x: x['confidence'])
        print(f"[DYNAMIC] Best result: confidence {best['confidence']:.2f}, method {best['method']}")
        return best
    
    return None
