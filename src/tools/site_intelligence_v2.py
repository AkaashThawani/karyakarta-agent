"""
Site Intelligence V2 - Learning from Chart Extractor

Uses UniversalExtractor's tree-based extraction to learn site structure:
1. Extract everything with tree-based method
2. Reverse-engineer selectors from successful extractions
3. Cache selectors per domain
4. Provide cached selectors on repeat visits

Key Features:
- Zero LLM calls for learning (uses tree extraction)
- Self-improving from successful extractions
- Transparent integration with existing tools
- Fast cached lookups on repeat visits
"""

from typing import List, Dict, Any, Optional
from playwright.async_api import Page
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
import json
import asyncio


class SiteIntelligenceV2:
    """
    Learn site structure using chart_extractor's tree extraction.
    No LLM needed - learns from DOM patterns.
    """
    
    def __init__(self, cache_dir: str = "selector_cache"):
        self.cache_dir = Path(__file__).parent.parent.parent / cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        print(f"[SI_V2] Initialized with cache dir: {self.cache_dir}")
    
    async def learn_from_extraction(
        self,
        page: Page,
        url: str,
        extracted_records: List[Dict[str, Any]],
        required_fields: List[str]
    ) -> Dict[str, str]:
        """
        Learn selectors by finding DOM elements that match extracted data.
        
        Args:
            page: Playwright page instance
            url: Page URL
            extracted_records: Records extracted by tree method
            required_fields: Fields that were extracted
            
        Returns:
            Dictionary mapping field names to CSS selectors
        """
        if not extracted_records:
            return {}
        
        domain = self._get_domain(url)
        print(f"[SI_V2] Learning selectors from {len(extracted_records)} records...")
        
        learned_selectors = {}
        
        # For each required field, find the selector
        for field in required_fields:
            # Get sample values from records
            sample_values = []
            for record in extracted_records[:3]:  # Use first 3 records
                value = record.get(field)
                if value and len(str(value)) > 2:
                    sample_values.append(str(value))
            
            if not sample_values:
                continue
            
            # Find selector for this field
            selector = await self._find_selector_for_field(
                page, 
                field, 
                sample_values
            )
            
            if selector:
                learned_selectors[field] = selector
                print(f"[SI_V2] ✓ Learned {field}: {selector}")
        
        # Save to cache
        if learned_selectors:
            self._save_selectors(domain, learned_selectors, required_fields)
            print(f"[SI_V2] ✅ Cached {len(learned_selectors)} selectors for {domain}")
        
        return learned_selectors
    
    async def _find_selector_for_field(
        self,
        page: Page,
        field: str,
        sample_values: List[str]
    ) -> Optional[str]:
        """
        Find CSS selector for elements containing sample values.
        
        Args:
            page: Playwright page
            field: Field name (e.g., 'title', 'summary')
            sample_values: Sample text values from this field
            
        Returns:
            CSS selector or None
        """
        if not sample_values:
            return None
        
        try:
            # Use JavaScript to find elements containing the text
            selector = await page.evaluate("""
                (field, samples) => {
                    // Find elements containing any of the sample texts
                    const allElements = document.querySelectorAll('*');
                    const candidates = [];
                    
                    for (const el of allElements) {
                        const text = el.textContent?.trim() || '';
                        
                        // Check if this element contains any sample value
                        for (const sample of samples) {
                            if (text.includes(sample) && text.length < sample.length * 3) {
                                // Element found, generate selector
                                let sel = el.tagName.toLowerCase();
                                
                                // Add class if available
                                if (el.className && typeof el.className === 'string') {
                                    const classes = el.className.split(' ').filter(c => c);
                                    if (classes.length > 0) {
                                        // Use first meaningful class
                                        const meaningfulClass = classes.find(c => 
                                            c.includes(field) || 
                                            c.includes('title') || 
                                            c.includes('heading') ||
                                            c.includes('text') ||
                                            c.includes('content')
                                        ) || classes[0];
                                        
                                        sel += '.' + meaningfulClass;
                                    }
                                }
                                
                                // Add attribute hints
                                if (el.getAttribute('data-field')) {
                                    sel += `[data-field="${el.getAttribute('data-field')}"]`;
                                }
                                
                                candidates.push({
                                    selector: sel,
                                    matchedText: text.substring(0, 50),
                                    depth: this._getDepth(el)
                                });
                                
                                break;
                            }
                        }
                    }
                    
                    // Return most common selector pattern
                    if (candidates.length > 0) {
                        // Group by selector
                        const counts = {};
                        for (const c of candidates) {
                            counts[c.selector] = (counts[c.selector] || 0) + 1;
                        }
                        
                        // Find most common
                        let bestSelector = '';
                        let maxCount = 0;
                        for (const [sel, count] of Object.entries(counts)) {
                            if (count > maxCount) {
                                maxCount = count;
                                bestSelector = sel;
                            }
                        }
                        
                        return bestSelector;
                    }
                    
                    return null;
                }
            """, field, sample_values[:3])  # Limit to 3 samples
            
            return selector if selector else None
            
        except Exception as e:
            print(f"[SI_V2] Failed to find selector for {field}: {e}")
            return None
    
    def get_cached_selectors(
        self,
        url: str,
        required_fields: List[str]
    ) -> Optional[Dict[str, str]]:
        """
        Get cached selectors for a domain.
        
        Args:
            url: Page URL
            required_fields: Fields needed
            
        Returns:
            Dictionary of field->selector mappings or None
        """
        domain = self._get_domain(url)
        cache = self._load_cache(domain)
        
        if not cache:
            return None
        
        selectors = cache.get('selectors', {})
        
        # Check if we have selectors for all required fields
        missing = [f for f in required_fields if f not in selectors]
        
        if missing:
            print(f"[SI_V2] Cache incomplete for {domain}, missing: {missing}")
            return None
        
        # Check cache age
        learned_at = cache.get('learned_at')
        if learned_at:
            age_days = (datetime.now() - datetime.fromisoformat(learned_at)).days
            if age_days > 30:
                print(f"[SI_V2] Cache expired for {domain} ({age_days} days old)")
                return None
        
        print(f"[SI_V2] ✓ Using cached selectors for {domain}")
        return selectors
    
    def _save_selectors(
        self,
        domain: str,
        selectors: Dict[str, str],
        fields: List[str]
    ):
        """Save learned selectors to cache."""
        cache_file = self.cache_dir / f"{domain}.json"
        
        # Load existing cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            except:
                cache = {}
        else:
            cache = {}
        
        # Update with new selectors
        if 'selectors' not in cache:
            cache['selectors'] = {}
        
        cache['selectors'].update(selectors)
        cache['learned_at'] = datetime.now().isoformat()
        cache['fields'] = fields
        cache['use_count'] = cache.get('use_count', 0) + 1
        
        # Save
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    
    def _load_cache(self, domain: str) -> Optional[Dict[str, Any]]:
        """Load cache for domain."""
        cache_file = self.cache_dir / f"{domain}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SI_V2] Error loading cache for {domain}: {e}")
            return None
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        
        # Remove www.
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    
    async def extract_with_cached_selectors(
        self,
        page: Page,
        selectors: Dict[str, str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Extract data using cached selectors.
        
        Args:
            page: Playwright page
            selectors: Field->selector mappings
            limit: Max records to extract
            
        Returns:
            List of extracted records
        """
        try:
            records = await page.evaluate("""
                (selectors, limit) => {
                    const records = [];
                    
                    // Get all elements for first field (to determine count)
                    const firstField = Object.keys(selectors)[0];
                    const firstSelector = selectors[firstField];
                    const elements = document.querySelectorAll(firstSelector);
                    
                    const count = Math.min(elements.length, limit);
                    
                    // Extract each record
                    for (let i = 0; i < count; i++) {
                        const record = {};
                        let hasData = false;
                        
                        for (const [field, selector] of Object.entries(selectors)) {
                            const els = document.querySelectorAll(selector);
                            if (els[i]) {
                                const text = els[i].textContent?.trim();
                                if (text) {
                                    record[field] = text;
                                    hasData = true;
                                }
                            }
                        }
                        
                        if (hasData) {
                            records.push(record);
                        }
                    }
                    
                    return records;
                }
            """, selectors, limit)
            
            print(f"[SI_V2] Extracted {len(records)} records using cached selectors")
            return records
            
        except Exception as e:
            print(f"[SI_V2] Failed to extract with cached selectors: {e}")
            return []
    
    def clear_cache(self, domain: Optional[str] = None):
        """
        Clear cache for specific domain or all domains.
        
        Args:
            domain: Specific domain to clear, or None for all
        """
        if domain:
            cache_file = self.cache_dir / f"{domain}.json"
            if cache_file.exists():
                cache_file.unlink()
                print(f"[SI_V2] Cleared cache for {domain}")
        else:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"[SI_V2] Cleared all cache")
