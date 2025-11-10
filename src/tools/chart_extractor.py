"""
Chart Extractor - Scraping-First with LLM Fallback

Extracts structured data from chart/list pages using:
1. Cached selectors (fastest)
2. Playwright locators (reliable)  
3. Heuristic patterns (fallback)
4. LLM (only for missing fields)

Architecture:
- Zero hardcoding - learns patterns
- Caches successful extractions
- LLM only as last resort
- Self-improving over time
"""

from typing import List, Dict, Any, Optional
from playwright.async_api import Page, Locator
from selectolax.parser import HTMLParser
from urllib.parse import urlparse
from datetime import datetime
import json
import re
import asyncio
import time


class PatternCache:
    """Cache successful extraction patterns per domain."""
    
    def __init__(self, cache_file: str = "source_cache/extraction_patterns.json"):
        from pathlib import Path
        self.cache_file = Path(__file__).parent.parent.parent / cache_file
        self.cache_file.parent.mkdir(exist_ok=True)
        self.patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.load()
    
    def load(self):
        """Load cached patterns."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.patterns = json.load(f)
                print(f"[CACHE] Loaded {len(self.patterns)} domain patterns")
            except Exception as e:
                print(f"[CACHE] Error loading: {e}")
    
    def save(self):
        """Save patterns to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.patterns, f, indent=2)
        except Exception as e:
            print(f"[CACHE] Error saving: {e}")
    
    def get_pattern(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get best cached pattern for domain."""
        if domain not in self.patterns:
            return None
        
        # Return most recently successful pattern
        patterns = self.patterns[domain]
        if patterns:
            # Sort by success rate and recency
            sorted_patterns = sorted(
                patterns,
                key=lambda p: (p.get("success_rate", 0), p.get("last_used", "")),
                reverse=True
            )
            return sorted_patterns[0].get("pattern")
        
        return None
    
    def save_pattern(
        self,
        domain: str,
        pattern: Dict[str, Any],
        fields: List[str],
        success_rate: float = 1.0
    ):
        """Cache successful pattern."""
        if domain not in self.patterns:
            self.patterns[domain] = []
        
        self.patterns[domain].append({
            "pattern": pattern,
            "fields": fields,
            "success_rate": success_rate,
            "last_used": datetime.now().isoformat(),
            "use_count": 1
        })
        
        # Keep only last 5 patterns per domain
        if len(self.patterns[domain]) > 5:
            self.patterns[domain] = self.patterns[domain][-5:]
        
        self.save()


class PlaywrightChartExtractor:
    """
    Extract charts using scraping-first approach.
    LLM only for missing fields.
    """
    
    def __init__(self):
        self.cache = PatternCache()
        self.last_successful_pattern: Optional[Dict[str, Any]] = None
        # NEW: Site Intelligence V2
        try:
            from src.tools.site_intelligence_v2 import SiteIntelligenceV2
            self.site_intelligence = SiteIntelligenceV2()
            print("[EXTRACT] Site Intelligence V2 enabled")
        except Exception as e:
            print(f"[EXTRACT] Site Intelligence V2 not available: {e}")
            self.site_intelligence = None
        # NEW: Learning Manager
        try:
            from src.tools.learning_manager import get_learning_manager
            self.learning_manager = get_learning_manager()
            print("[EXTRACT] Learning Manager enabled")
        except Exception as e:
            print(f"[EXTRACT] Learning Manager not available: {e}")
            self.learning_manager = None
    
    def _format_timestamp(self) -> str:
        """Format timestamp to match chart_tool format: HH:MM:SS.mmm"""
        t = time.time()
        return f"{time.strftime('%H:%M:%S', time.localtime(t))}.{int((t % 1) * 1000):03d}"
    
    async def extract_chart(
        self,
        page: Page,
        url: str,
        required_fields: List[str],
        limit: Optional[int] = None,
        result_storage: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract chart data using multi-layer approach.

        Args:
            page: Playwright page instance
            url: URL to extract from (can be string or list - takes first if list)
            required_fields: List of field names to extract
            limit: Maximum number of records (enables early termination)
            result_storage: Optional external list to progressively save results (survives timeout)

        Priority:
        1. UniversalExtractor (extract EVERYTHING, then search)
        2. pandas.read_html() (tables only)
        3. Cached selectors (learned patterns)
        4. Playwright locators (fast)
        5. Heuristic patterns (fallback)
        6. LLM extraction (last resort)
        """
        # Handle URL parameter - can be string or list (take first if list)
        if isinstance(url, list):
            if url:
                url = url[0]  # Take first URL
                print(f"[EXTRACT] Received URL list, using first: {url}")
            else:
                print(f"[EXTRACT] Received empty URL list")
                return []

        if not isinstance(url, str):
            print(f"[EXTRACT] Invalid URL type: {type(url)}, expected string")
            return []

        domain = urlparse(url).netloc
        
        print(f"\n[EXTRACT] Starting extraction from {domain}")
        print(f"[EXTRACT] Required fields: {required_fields}")
        
        # NEW: Check if page actually loaded (Fix for failed playwright_execute navigation)
        current_url = page.url
        if current_url == "about:blank" or domain not in current_url:
            nav_start = time.time()
            print(f"[EXTRACT] ⏱️ {self._format_timestamp()} - Page not loaded (URL: {current_url}), navigating now...")
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=10000)
                nav_duration = time.time() - nav_start
                print(f"[EXTRACT] ⏱️ {self._format_timestamp()} - Navigation successful in {nav_duration:.2f}s")
            except Exception as nav_error:
                print(f"[EXTRACT] ❌ Navigation failed: {nav_error}")
                raise Exception(f"Failed to navigate to {url}: {nav_error}")
        
        # Quick wait for content to load (2s max)
        try:
            await asyncio.sleep(2)
        except:
            pass  # Continue anyway
        
        print(f"[EXTRACT] ⏱️ {self._format_timestamp()} - Page ready, starting extraction")
        
        # NEW: Step 0 - Check for cached selectors from Site Intelligence V2
        if self.site_intelligence:
            cached_selectors = self.site_intelligence.get_cached_selectors(url, required_fields)
            if cached_selectors:
                print(f"[EXTRACT] 🚀 Using cached selectors from Site Intelligence V2")
                cached_records = await self.site_intelligence.extract_with_cached_selectors(
                    page, 
                    cached_selectors, 
                    limit=limit or 10
                )
                if cached_records and len(cached_records) >= 3:
                    print(f"[EXTRACT] ✅ Cached selectors extracted {len(cached_records)} records!")
                    return cached_records
                else:
                    print(f"[EXTRACT] Cached selectors failed, falling back to tree extraction")
        
        # NEW: Step 1 - Try UniversalExtractor with tree-based method first!
        print(f"[EXTRACT] 🌳 Trying tree-based extraction (BFS+DFS+flattening)...")
        import time
        tree_start_time = time.time()
        try:
            from src.tools.universal_extractor import UniversalExtractor, SmartSearcher
            
            # CRITICAL: Wrap page.content() in timeout!
            html = await asyncio.wait_for(page.content(), timeout=5.0)
            
            # NEW: Use tree-based extraction with global limit and required fields
            extractor = UniversalExtractor()
            
            # Try tree-based extraction first (more accurate with global limit)
            tree_records = await extractor.extract_with_tree_structure_async(
                html=html,
                limit=limit or 10,
                required_fields=required_fields,
                result_storage=result_storage  # Pass storage for progressive saving
            )
            
            if tree_records and len(tree_records) >= 3:
                tree_time = time.time() - tree_start_time
                print(f"[EXTRACT] ✅ Tree-based extraction found {len(tree_records)} records!")
                
                # NEW: Record successful tree extraction
                if self.learning_manager:
                    self.learning_manager.record_tool_execution(
                        url, "tree_extraction", success=True, response_time=tree_time
                    )
                
                # NEW: Learn from successful extraction
                if self.site_intelligence:
                    print(f"[EXTRACT] 🎓 Learning selectors for future visits...")
                    await self.site_intelligence.learn_from_extraction(
                        page, 
                        url, 
                        tree_records, 
                        required_fields
                    )
                
                return tree_records
            
            print(f"[EXTRACT] Tree-based found {len(tree_records)} records, trying legacy method...")
            
            # Fallback to legacy extraction
            all_data = await extractor.extract_everything_async(html, url, limit=limit)
            
            print(f"[EXTRACT] Extracted:")
            print(f"  - {all_data['summary']['tables_count']} tables")
            print(f"  - {all_data['summary']['lists_count']} lists")
            print(f"  - {all_data['summary']['cards_count']} cards")
            print(f"  - {all_data['summary']['total_elements']} total elements")
            
            # DEBUG: Save full extraction dump
            try:
                from pathlib import Path
                dump_path = Path(__file__).parent.parent.parent / 'extraction_dump.json'
                with open(dump_path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, indent=2, ensure_ascii=False)
                print(f"[EXTRACT] 📝 Saved full dump to: {dump_path}")
            except Exception as e:
                print(f"[EXTRACT] Failed to save dump: {e}")
            
            # DEBUG: Print sample cards
            cards = all_data.get('cards', [])
            print(f"\n[EXTRACT] 📊 Sample of first 5 cards:")
            for i, card in enumerate(cards[:5]):
                print(f"  Card {i+1}: {json.dumps(card, ensure_ascii=False)[:200]}...")
            print()
            
            # Search for relevant data
            searcher = SmartSearcher()
            query = ' '.join(required_fields)  # Build query from fields
            records = searcher.search(all_data, query, required_fields)
            
            # If search found matches, return them
            if records and len(records) >= 3:
                print(f"[EXTRACT] ✅ SmartSearcher found {len(records)} matching records!")
                
                # NEW: Learn from successful extraction
                if self.site_intelligence:
                    print(f"[EXTRACT] 🎓 Learning selectors for future visits...")
                    await self.site_intelligence.learn_from_extraction(
                        page, 
                        url, 
                        records[:10],  # Use first 10 for learning
                        required_fields
                    )
                
                return records[:50]
            
            # If search didn't find matches but we have cards, return them anyway
            # Let synthesis LLM do the smart filtering
            if all_data.get('cards') and len(all_data['cards']) >= 3:
                print(f"[EXTRACT] SmartSearcher found no matches, but returning {len(all_data['cards'])} cards for LLM synthesis")
                
                # NEW: Learn from cards
                if self.site_intelligence:
                    print(f"[EXTRACT] 🎓 Learning selectors from cards...")
                    await self.site_intelligence.learn_from_extraction(
                        page, 
                        url, 
                        all_data['cards'][:10],
                        required_fields
                    )
                
                return all_data['cards'][:50]
            
            print(f"[EXTRACT] UniversalExtractor found insufficient data")
            
            # Record tree extraction failure
            if self.learning_manager:
                tree_time = time.time() - tree_start_time
                self.learning_manager.record_tool_execution(
                    url, "tree_extraction", success=False, response_time=tree_time
                )
        except Exception as e:
            print(f"[EXTRACT] UniversalExtractor failed: {e}")
            # Record tree extraction failure
            if self.learning_manager:
                tree_time = time.time() - tree_start_time
                self.learning_manager.record_tool_execution(
                    url, "tree_extraction", success=False, response_time=tree_time
                )
        
        # NEW: Check if this is a new site
        cached = self.cache.get_pattern(domain)
        # DISABLED: Site Intelligence (stuck/slow - needs more capable agent)
        # if not cached:
        #     print(f"[EXTRACT] 🆕 New site detected: {domain}")
        #     print(f"[EXTRACT] 🧠 Running Site Intelligence first...")
        #     await self._run_site_intelligence(page, url, required_fields)
        #     # Reload cache after intelligence runs
        #     cached = self.cache.get_pattern(domain)
        
        # Step 1: Try cached selectors
        if cached:
            print(f"[EXTRACT] Trying cached pattern...")
            try:
                # Add 10 second timeout to prevent hanging
                records = await asyncio.wait_for(
                    self._extract_with_selectors(page, cached),
                    timeout=10.0
                )
                validation = self._validate_completeness(records, required_fields, url)
                if validation.get('coverage', 0.0) >= 0.8:
                    print(f"[EXTRACT] ✅ Cached pattern worked!")
                    return records
                else:
                    print(f"[EXTRACT] Cached pattern had low coverage ({validation.get('coverage', 0.0):.0%})")
            except asyncio.TimeoutError:
                print(f"[EXTRACT] ⏱️ Cached pattern timeout after 10s, continuing to LLM fallback...")
        
        # DISABLED: Playwright locators - causes hangs, UniversalExtractor already extracts everything
        # print(f"[EXTRACT] Trying Playwright locators...")
        # records = await self._extract_with_locators(page, required_fields)
        # if records:
        #     validation = self._validate_completeness(records, required_fields, url)
        #     if validation.get('coverage', 0.0) >= 0.6:
        #         print(f"[EXTRACT] ✅ Playwright locators worked!")
        #         if self.last_successful_pattern:
        #             self.cache.save_pattern(
        #                 domain,
        #                 self.last_successful_pattern,
        #                 list(records[0].keys()) if records else []
        #             )
        #         
        #         if not validation.get('complete', False):
        #             coverage = validation.get('coverage', 0.0)
        #             print(f"[EXTRACT] Coverage: {coverage*100:.0f}%, using LLM for missing fields...")
        #             records = await self._llm_fill_missing_fields(page, records, required_fields)
        #         
        #         return records
        
        # DISABLED: Heuristics - Let synthesis LLM handle filtering
        # print(f"[EXTRACT] Trying heuristic patterns...")
        # try:
        #     records = await self._extract_with_heuristics(page, required_fields)
        # except asyncio.TimeoutError:
        #     print(f"[EXTRACT] ⚠️ Heuristic extraction timeout")
        #     records = []
        # if records:
        #     validation = self._validate_completeness(records, required_fields, url)
        #     coverage = validation.get('coverage', 0.0)
        #     print(f"[EXTRACT] Heuristic extraction coverage: {coverage*100:.0f}%")
        #     
        #     if not validation.get('complete', False):
        #         print(f"[EXTRACT] Using LLM for missing fields...")
        #         records = await self._llm_fill_missing_fields(page, records, required_fields)
        #     
        #     return records
        
        # Step 4: Full LLM fallback
        print(f"[EXTRACT] All scraping failed, using full LLM extraction...")
        llm_start_time = time.time()
        records = await self._llm_extract_all(page, required_fields)
        llm_time = time.time() - llm_start_time
        
        # NEW: Record LLM extraction result
        if self.learning_manager:
            success = bool(records and len(records) >= 3)
            self.learning_manager.record_tool_execution(
                url, "llm_extraction", success=success, response_time=llm_time
            )
        
        # NEW: If LLM succeeded, learn from it!
        if records:
            print(f"[EXTRACT] ✨ LLM extracted {len(records)} records!")
            await self._learn_from_llm_success(page, url, records, required_fields)
        
        return records
    
    async def _extract_with_selectors(
        self,
        page: Page,
        pattern: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract using cached selectors."""
        try:
            records = []
            container_sel = pattern.get("container")
            row_sel = pattern.get("row")
            field_sels = pattern.get("fields", {})
            
            if not all([container_sel, row_sel]):
                return []
            
            # Get rows
            rows = page.locator(f"{container_sel} {row_sel}")
            count = await rows.count()
            
            for i in range(min(count, 10)):
                row = rows.nth(i)
                record = {}
                
                # Extract each field
                for field, selector in field_sels.items():
                    try:
                        elem = row.locator(selector).first
                        if await elem.count() > 0:
                            text = await elem.text_content()
                            record[field] = text.strip() if text else ""
                    except:
                        pass
                
                if record:
                    records.append(record)
            
            return records
        
        except Exception as e:
            print(f"[EXTRACT] Selector extraction failed: {e}")
            return []
    
    async def _extract_with_locators(
        self,
        page: Page,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract using Playwright locators."""
        records = []
        
        # Try table first
        table = page.locator('table').first
        if await table.count() > 0:
            print(f"[EXTRACT] Found table, extracting...")
            rows = table.locator('tbody tr, tr')
            count = await rows.count()
            
            # Store pattern for caching
            self.last_successful_pattern = {
                "container": "table",
                "row": "tr",
                "fields": {}
            }
            
            for i in range(min(count, 10)):
                row = rows.nth(i)
                cells = row.locator('td, th')
                cell_count = await cells.count()
                
                if cell_count == 0:
                    continue
                
                record = {}
                
                # Extract cells
                for j in range(cell_count):
                    cell = cells.nth(j)
                    text = await cell.text_content()
                    if text:
                        text = text.strip()
                        # Map to field
                        field = self._guess_field_from_position(j, cell_count, required_fields)
                        if field:
                            record[field] = text
                            # Store in pattern
                            self.last_successful_pattern["fields"][field] = f"td:nth-child({j+1})"
                
                if len(record) >= 2:
                    records.append(record)
        
        # Try list if no table
        if not records:
            print(f"[EXTRACT] No table, trying list...")
            items = page.locator('li, div[class*="item"], div[class*="row"], div[class*="card"]')
            count = await items.count()
            
            if count > 0:
                self.last_successful_pattern = {
                    "container": "body",
                    "row": "li, div[class*='item']",
                    "fields": {}
                }
                
                for i in range(min(count, 10)):
                    item = items.nth(i)
                    record = await self._extract_from_item(item, required_fields)
                    if record:
                        records.append(record)
        
        return records
    
    async def _extract_from_item(
        self,
        item: Locator,
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """Extract fields from a single item."""
        record = {}
        
        # Get full text for regex extraction
        full_text = await item.text_content() or ""
        item_html = await item.inner_html() or ""
        
        for field in required_fields:
            value = None
            
            # Special handling for phone numbers
            if 'phone' in field.lower() or 'number' in field.lower():
                value = self._extract_phone_number(full_text)
                if value:
                    record[field] = value
                    continue
            
            # Special handling for websites/URLs
            if 'website' in field.lower() or 'url' in field.lower() or 'link' in field.lower():
                value = await self._extract_website(item, item_html)
                if value:
                    record[field] = value
                    continue
            
            # Try by class
            for variant in [field, field.replace("_", "-"), field.replace("_", "")]:
                locator = item.locator(f'[class*="{variant}" i]').first
                if await locator.count() > 0:
                    value = await locator.text_content()
                    if value:
                        break
            
            # Try by data attribute
            if not value:
                locator = item.locator(f'[data-field="{field}"], [data-{field}]').first
                if await locator.count() > 0:
                    value = await locator.text_content()
            
            # Try common tags
            if not value:
                if field in ['song', 'title', 'name']:
                    locator = item.locator('h1, h2, h3, h4, strong, b, a').first
                    if await locator.count() > 0:
                        value = await locator.text_content()
                elif field in ['description', 'desc']:
                    locator = item.locator('p, span').first
                    if await locator.count() > 0:
                        value = await locator.text_content()
            
            if value:
                record[field] = value.strip()
        
        return record
    
    def _extract_phone_number(self, text: str) -> Optional[str]:
        """Extract phone number using regex patterns."""
        if not text:
            return None
        
        # Common phone patterns
        patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (702) 123-4567, 702-123-4567
            r'\+\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}',  # +1-702-123-4567
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # 702-123-4567
            r'\d{10}',  # 7021234567
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0)
                # Clean up
                phone = re.sub(r'[^\d+()-]', '', phone)
                if len(phone) >= 10:  # Valid phone should have at least 10 digits
                    return phone
        
        return None
    
    async def _extract_website(self, item: Locator, html: str) -> Optional[str]:
        """Extract website URL from item."""
        # Try to find link elements
        try:
            links = item.locator('a[href]')
            count = await links.count()
            
            for i in range(count):
                link = links.nth(i)
                href = await link.get_attribute('href')
                
                if href and self._is_valid_website(href):
                    return href
        except:
            pass
        
        # Fallback: regex search for URLs in HTML
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        match = re.search(url_pattern, html)
        if match:
            url = match.group(0)
            if self._is_valid_website(url):
                return url
        
        return None
    
    def _is_valid_website(self, url: str) -> bool:
        """Check if URL is a valid website (not social media, not internal link)."""
        if not url:
            return False
        
        # Skip relative URLs
        if url.startswith('/') or url.startswith('#'):
            return False
        
        # Skip mailto: and tel: links
        if url.startswith(('mailto:', 'tel:', 'javascript:')):
            return False
        
        # Skip common non-website URLs
        skip_domains = [
            'facebook.com', 'twitter.com', 'instagram.com',
            'linkedin.com', 'youtube.com', 'pinterest.com',
            'maps.google.com', 'google.com/maps'
        ]
        
        url_lower = url.lower()
        if any(domain in url_lower for domain in skip_domains):
            return False
        
        return True
    
    async def _extract_with_heuristics(
        self,
        page: Page,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract using heuristic patterns."""
        # CRITICAL: Wrap page.content() in timeout!
        html = await asyncio.wait_for(page.content(), timeout=5.0)
        
        from src.tools.element_parser import ElementParser
        parser = ElementParser()
        
        tree = HTMLParser(html)
        
        # Find containers
        containers = tree.css('table, ol, ul, [role="list"], div[class*="chart"], div[class*="list"]')
        
        for container in containers:
            records = self._parse_container(container, required_fields)
            if len(records) >= 3:  # At least 3 items found
                return records
        
        return []
    
    def _parse_container(
        self,
        container: Any,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Parse container heuristically."""
        records = []
        
        # Get rows
        rows = container.css('tr, li, div[class*="item"], div[class*="entry"], div[class*="row"]')
        
        for row in rows[:10]:
            # Get all text nodes
            texts = []
            for node in row.traverse():
                if node.tag in ['script', 'style']:
                    continue
                text = node.text(strip=True)
                if text and len(text) > 1:
                    texts.append(text)
            
            if len(texts) < 2:
                continue
            
            # Try to map texts to fields
            record = {}
            
            # Rank usually first number
            if 'rank' in required_fields and texts:
                match = re.search(r'^(\d+)', texts[0])
                if match:
                    record['rank'] = int(match.group(1))
            
            # Map remaining by position
            for i, text in enumerate(texts[:len(required_fields)]):
                if i < len(required_fields):
                    field = required_fields[i]
                    if field not in record:
                        record[field] = text
            
            if len(record) >= 2:
                records.append(record)
        
        return records
    
    async def _llm_fill_missing_fields(
        self,
        page: Page,
        records: List[Dict[str, Any]],
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Use LLM ONLY for missing fields."""
        if not records:
            return records
        
        # Find missing fields
        present_fields = set(records[0].keys())
        missing_fields = set(required_fields) - present_fields
        
        if not missing_fields:
            return records
        
        print(f"[EXTRACT] LLM filling missing fields: {missing_fields}")
        
        try:
            # CRITICAL: Wrap page.content() in timeout!
            html = await asyncio.wait_for(page.content(), timeout=5.0)
            tree = HTMLParser(html)
            
            # Remove scripts/styles
            for tag in tree.css('script, style'):
                tag.decompose()
            
            # Get text content
            body = tree.body
            simplified = body.text(strip=True) if body else ""
            if not simplified and tree.html:
                simplified = str(tree.html)[:5000]
            else:
                simplified = simplified[:5000]  # Limit size
            
            # Build prompt
            prompt = f"""Extract ONLY these fields: {list(missing_fields)}

Context:
{simplified}

Return JSON array with ONLY missing fields for top 10 items:
[{{{", ".join(f'"{f}": "value"' for f in missing_fields)}}}, ...]

JSON:"""
            
            # Call LLM
            from src.services.llm_service import LLMService
            from src.core.config import settings
            llm = LLMService(settings)
            model = llm.get_model()
            response = model.invoke(prompt)
            
            content = response.content if hasattr(response, 'content') else str(response)
            content_str = str(content) if content else ""
            json_match = re.search(r'\[.*\]', content_str, re.DOTALL)
            
            if json_match:
                llm_data = json.loads(json_match.group())
                
                # Merge with existing
                for i, record in enumerate(records):
                    if i < len(llm_data):
                        record.update(llm_data[i])
        
        except Exception as e:
            print(f"[EXTRACT] LLM fill failed: {e}")
        
        return records
    
    async def _llm_extract_all(
        self,
        page: Page,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Full LLM extraction (last resort)."""
        print(f"[EXTRACT] Using full LLM extraction...")
        
        try:
            # CRITICAL: Wrap page.content() in timeout!
            html = await asyncio.wait_for(page.content(), timeout=5.0)
            tree = HTMLParser(html)
            
            for tag in tree.css('script, style'):
                tag.decompose()
            
            # Get text content
            body = tree.body
            simplified = body.text(strip=True) if body else ""
            if not simplified and tree.html:
                simplified = str(tree.html)[:8000]
            else:
                simplified = simplified[:8000]
            
            prompt = f"""Extract top 10 items with these fields: {required_fields}

Content:
{simplified}

Return JSON array:
[{{{", ".join(f'"{f}": "value"' for f in required_fields)}}}, ...]

JSON:"""
            
            from src.services.llm_service import LLMService
            from src.core.config import settings
            llm = LLMService(settings)
            model = llm.get_model()
            response = model.invoke(prompt)
            
            content = response.content if hasattr(response, 'content') else str(response)
            content_str = str(content) if content else ""
            json_match = re.search(r'\[.*\]', content_str, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
        
        except Exception as e:
            print(f"[EXTRACT] Full LLM extraction failed: {e}")
        
        return []
    
    def _validate_completeness(
        self,
        records: List[Dict[str, Any]],
        required_fields: List[str],
        url: str = ''
    ) -> Dict[str, Any]:
        """
        Check completeness and return validation results.
        
        Args:
            records: Extracted records
            required_fields: Required field names
            url: Optional URL for context
            
        Returns:
            Validation dictionary with completeness info
        """
        try:
            from src.routing.result_validator import ResultValidator
            
            validator = ResultValidator()
            validation = validator.validate(
                records,
                required_fields,
                {'url': url} if url else None
            )
            
            return validation
            
        except Exception as e:
            print(f"[EXTRACT] Validation failed: {e}")
            # Fallback
            if not records:
                return {
                    'complete': False,
                    'coverage': 0.0,
                    'missing_fields': required_fields
                }
            
            present = set(records[0].keys())
            required = set(required_fields)
            coverage = len(present & required) / len(required) if required else 1.0
            
            return {
                'complete': len(required - present) == 0,
                'coverage': coverage,
                'missing_fields': list(required - present)
            }
    
    def _guess_field_from_position(
        self,
        position: int,
        total: int,
        required_fields: List[str]
    ) -> Optional[str]:
        """Guess field from column position."""
        # Common patterns
        if position == 0:
            if 'rank' in required_fields:
                return 'rank'
            elif 'song' in required_fields:
                return 'song'
        elif position == 1:
            if 'song' in required_fields:
                return 'song'
            elif 'artist' in required_fields:
                return 'artist'
        elif position == 2 and 'artist' in required_fields:
            return 'artist'
        elif position < len(required_fields):
            return required_fields[position]
        
        return None
    
    async def _run_site_intelligence(
        self,
        page: Page,
        url: str,
        required_fields: List[str]
    ):
        """
        Run Site Intelligence to learn site structure on first visit.
        """
        try:
            from src.tools.site_intelligence import SiteIntelligenceTool
            from src.services.llm_service import LLMService
            from src.core.config import settings
            
            intelligence = SiteIntelligenceTool()
            llm_service = LLMService(settings)
            
            # Learn site structure
            schema = await intelligence.build_site_schema(url, page, llm_service)
            
            if schema and schema.get("elements"):
                domain = urlparse(url).netloc
                
                # Extract selectors from learned elements
                learned_selectors = {}
                for name, element_data in schema.get("elements", {}).items():
                    # Map field names if they match required fields
                    for field in required_fields:
                        if field.lower() in name.lower():
                            learned_selectors[field] = element_data.get("selector", "")
                            break
                
                if learned_selectors:
                    # Save learned selectors to cache
                    pattern = {
                        "container": "body",
                        "row": "div, li",  # Generic
                        "fields": learned_selectors
                    }
                    
                    self.cache.save_pattern(
                        domain,
                        pattern,
                        list(learned_selectors.keys()),
                        success_rate=0.8  # Initial learning confidence
                    )
                    
                    print(f"[EXTRACT] 🎓 Learned {len(learned_selectors)} selectors from Site Intelligence")
                else:
                    print(f"[EXTRACT] ⚠️ Site Intelligence learned {len(schema.get('elements', {}))} elements but none matched required fields")
            else:
                print(f"[EXTRACT] ⚠️ Site Intelligence couldn't learn structure")
                
        except Exception as e:
            print(f"[EXTRACT] Site Intelligence failed: {e}")
            # Continue without intelligence - will fall back to other methods
    
    async def _learn_from_llm_success(
        self,
        page: Page,
        url: str,
        records: List[Dict[str, Any]],
        required_fields: List[str]
    ):
        """
        NEW: Learn selectors from successful LLM extraction.
        Reverse-engineers selectors by finding elements with LLM-extracted values.
        """
        if not records:
            return
        
        domain = urlparse(url).netloc
        print(f"[EXTRACT] 🎓 LLM succeeded! Learning selectors from results...")
        
        try:
            learned_selectors = {}
            
            # Sample first 3 records for learning
            for field in required_fields:
                for record in records[:3]:
                    value = record.get(field)
                    if value and len(str(value)) > 2:
                        # Find element containing this text
                        selector = await self._find_selector_for_text(page, str(value), field)
                        if selector:
                            learned_selectors[field] = selector
                            print(f"[EXTRACT] 📚 Learned {field}: {selector}")
                            break
            
            if learned_selectors:
                # Save to cache
                pattern = {
                    "container": "body",
                    "row": "div, li",  # Generic fallback
                    "fields": learned_selectors
                }
                
                self.cache.save_pattern(
                    domain,
                    pattern,
                    list(learned_selectors.keys()),
                    success_rate=0.9  # High confidence from LLM
                )
                
                print(f"[EXTRACT] ✅ Cached {len(learned_selectors)} selectors for future visits!")
                
        except Exception as e:
            print(f"[EXTRACT] Failed to learn from LLM: {e}")
    
    async def _find_selector_for_text(
        self,
        page: Page,
        text: str,
        field_hint: str
    ) -> Optional[str]:
        """
        Find CSS selector for element containing specific text.
        """
        try:
            # Escape text for selector
            escaped_text = text.replace('"', '\\"').replace("'", "\\'")
            
            # Try exact text match
            locator = page.locator(f'text="{escaped_text}"')
            if await locator.count() > 0:
                first = locator.first
                
                # Get element tag and attributes
                tag = await first.evaluate('el => el.tagName.toLowerCase()')
                class_name = await first.evaluate('el => el.className')
                
                # Build selector
                if class_name:
                    # Use first class only
                    first_class = class_name.split()[0] if class_name else ""
                    if first_class:
                        selector = f"{tag}.{first_class}"
                        return selector
                
                # Fallback to tag with attribute hints
                if 'title' in field_hint or 'name' in field_hint:
                    return f"{tag}:has-text('{text[:20]}')"
                elif 'location' in field_hint:
                    return f"{tag}[class*='location']"
                else:
                    return f"{tag}"
            
            return None
            
        except Exception as e:
            print(f"[EXTRACT] Selector search failed for '{text}': {e}")
            return None
