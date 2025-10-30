"""
Site-Based Selector Map with Lazy Loading

Manages selector mappings with site-specific learning and automatic caching.
Uses separate JSON files per domain for scalability.

Architecture:
- O(1) lookups (site → tool → hint → selector)
- Lazy loading (only load sites when needed)
- Site-specific learning (no promotion conflicts)
- Automatic caching per domain
- 99% token reduction

Example:
    from src.routing.selector_map import get_selector_map
    
    selector_map = get_selector_map()
    selector = selector_map.get_selector(
        url="https://spotify.com/search",
        tool="playwright_execute",
        hint="search_input"
    )
"""

import json
import os
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse


class SelectorMap:
    """
    Site-based selector map with lazy loading and smart caching.
    
    Structure: website → tool → selector_hint → selector data
    Storage: One JSON file per domain in selector_cache/
    """
    
    def __init__(self, cache_dir: str = "selector_cache"):
        """
        Initialize selector map with lazy loading.
        
        Args:
            cache_dir: Directory for selector cache files
        """
        self.cache_dir = Path(__file__).parent.parent.parent / cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        
        # In-memory cache (only loaded sites)
        self.loaded_sites: Dict[str, dict] = {}
        
        # Load generic fallback (always needed)
        self.generic = self._load_site("generic")
        
        print(f"[SELECTOR_MAP] Initialized with cache dir: {self.cache_dir}")
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.
        
        Args:
            url: Full URL
            
        Returns:
            Domain name (e.g., "spotify.com")
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return "unknown"
    
    def _load_site(self, domain: str) -> dict:
        """
        Load site-specific selector map from file.
        Uses in-memory cache to avoid repeated file reads.
        
        Args:
            domain: Domain name
            
        Returns:
            Site selector map or empty dict
        """
        # Check in-memory cache first
        if domain in self.loaded_sites:
            return self.loaded_sites[domain]
        
        # Load from file
        file_path = self.cache_dir / f"{domain}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.loaded_sites[domain] = data
                    print(f"[SELECTOR_MAP] Loaded cache for {domain}")
                    return data
            except Exception as e:
                print(f"[SELECTOR_MAP] Error loading {domain}: {e}")
        
        # Return empty dict if not found
        return {}
    
    def _save_site(self, domain: str, data: dict):
        """
        Save site-specific selector map to file.
        
        Args:
            domain: Domain name
            data: Selector map data
        """
        try:
            file_path = self.cache_dir / f"{domain}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.loaded_sites[domain] = data
            
            # Enhanced logging with details
            total_hints = sum(len(tool_data) for tool_data in data.values())
            print(f"\n{'='*60}")
            print(f"💾 SELECTOR CACHE UPDATED")
            print(f"{'='*60}")
            print(f"Domain: {domain}")
            print(f"File: {file_path}")
            print(f"Total hints: {total_hints}")
            print(f"Tools: {', '.join(data.keys())}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"[SELECTOR_MAP] Error saving {domain}: {e}")
    
    def get_selector(
        self,
        url: str,
        tool: str,
        hint: str
    ) -> Optional[str]:
        """
        Get best selector for domain + tool + hint.
        Returns None if not found, triggering Site Intelligence learning.
        
        Args:
            url: Target URL
            tool: Tool name (e.g., "playwright_execute")
            hint: Selector hint (e.g., "search_input")
            
        Returns:
            Best selector or None (triggers learning)
        """
        domain = self._extract_domain(url)
        
        # Load site cache
        site_data = self._load_site(domain)
        
        # If no cache exists at all, return None to trigger learning
        if not site_data:
            print(f"[SELECTOR_MAP] No cache for {domain}, needs Site Intelligence learning")
            return None
        
        # Try site-specific learned selectors first
        best = site_data.get(tool, {}).get(hint, {}).get("best")
        
        if best:
            print(f"[SELECTOR_MAP] Found cached selector for {domain}/{tool}/{hint}")
            return best
        
        # Try site intelligence (LLM-learned elements)
        intelligence = site_data.get("site_intelligence", {})
        if intelligence:
            elements = intelligence.get("elements", {})
            
            # Try exact match first
            if hint in elements:
                selector = elements[hint].get("selector")
                if selector:
                    print(f"[SELECTOR_MAP] Found selector from site intelligence for {hint}")
                    return selector
            
            # Try fuzzy match (search_input → main_search_input, etc.)
            for elem_name, elem_data in elements.items():
                if hint in elem_name or elem_name in hint:
                    selector = elem_data.get("selector")
                    if selector:
                        print(f"[SELECTOR_MAP] Found similar selector from site intelligence: {elem_name}")
                        return selector
        
        # Cache exists but selector not found - return None to re-trigger learning
        print(f"[SELECTOR_MAP] Cache exists for {domain} but selector '{hint}' not found, needs re-learning")
        return None
    
    def get_selectors(self, hint: str) -> List[str]:
        """
        Backward compatibility: Get generic selectors for a hint.
        This is for compatibility with old code.
        
        Args:
            hint: Selector hint
            
        Returns:
            List of fallback selectors
        """
        # Return generic fallbacks
        fallbacks = self.generic.get("playwright_execute", {}).get(hint, {}).get("fallbacks", [])
        if fallbacks:
            print(f"[SELECTOR_MAP] Retrieved {len(fallbacks)} generic selectors for '{hint}'")
        return fallbacks
    
    def get_fallbacks(
        self,
        url: str,
        tool: str,
        hint: str
    ) -> List[str]:
        """
        Get fallback selectors if best selector fails.
        
        Args:
            url: Target URL
            tool: Tool name
            hint: Selector hint
            
        Returns:
            List of fallback selectors
        """
        domain = self._extract_domain(url)
        
        # Try site-specific first
        site_data = self._load_site(domain)
        fallbacks = site_data.get(tool, {}).get(hint, {}).get("fallbacks", [])
        
        if fallbacks:
            return fallbacks
        
        # Fallback to generic
        return self.generic.get(tool, {}).get(hint, {}).get("fallbacks", [])
    
    def promote_selector(
        self,
        url: str,
        tool: str,
        hint: str,
        selector: str,
        success: bool = True,
        response_time: float = None
    ):
        """
        Promote or demote selector based on success.
        Updates site-specific file automatically.
        
        Args:
            url: Target URL
            tool: Tool name
            hint: Selector hint
            selector: CSS selector that was tried
            success: Whether selector worked
            response_time: Time taken (seconds)
        """
        domain = self._extract_domain(url)
        
        # Load or create site data
        site_data = self._load_site(domain)
        if not site_data:
            site_data = {}
        
        # Ensure structure exists
        if tool not in site_data:
            site_data[tool] = {}
        if hint not in site_data[tool]:
            site_data[tool][hint] = {
                "best": None,
                "selectors": {},
                "fallbacks": []
            }
        
        hint_data = site_data[tool][hint]
        
        # Update selector stats
        if selector not in hint_data["selectors"]:
            hint_data["selectors"][selector] = {
                "success": 0,
                "fail": 0,
                "last_used": 0,
                "avg_response_time": 0
            }
        
        stats = hint_data["selectors"][selector]
        
        if success:
            stats["success"] += 1
            stats["last_used"] = time.time()
            
            # Update average response time
            if response_time is not None:
                n = stats["success"]
                old_avg = stats["avg_response_time"]
                stats["avg_response_time"] = (old_avg * (n-1) + response_time) / n
            
            # Promote to "best" if qualified
            # Criteria: >= 3 successes, >90% success rate
            total = stats["success"] + stats["fail"]
            success_rate = stats["success"] / total if total > 0 else 0
            
            if stats["success"] >= 3 and success_rate > 0.9:
                current_best = hint_data["best"]
                
                if not current_best:
                    hint_data["best"] = selector
                    print(f"\n🎯 SELECTOR PROMOTED")
                    print(f"   Domain: {domain}")
                    print(f"   Hint: {hint}")
                    print(f"   Selector: {selector}")
                    print(f"   Success Rate: {success_rate:.1%}")
                    print(f"   Avg Response: {stats['avg_response_time']:.2f}s\n")
                else:
                    # Compare with current best
                    best_stats = hint_data["selectors"].get(current_best, {})
                    best_avg = best_stats.get("avg_response_time", float('inf'))
                    if stats["avg_response_time"] < best_avg:
                        hint_data["best"] = selector
                        print(f"\n⚡ SELECTOR REPLACED (faster)")
                        print(f"   Domain: {domain}")
                        print(f"   Hint: {hint}")
                        print(f"   Old: {current_best} ({best_avg:.2f}s)")
                        print(f"   New: {selector} ({stats['avg_response_time']:.2f}s)")
                        if best_avg != float('inf'):
                            improvement = ((best_avg - stats['avg_response_time'])/best_avg*100)
                            print(f"   Improvement: {improvement:.1f}%\n")
                        else:
                            print(f"   Improvement: significant\n")
        else:
            stats["fail"] += 1
            
            # Demote if too many failures
            total = stats["success"] + stats["fail"]
            fail_rate = stats["fail"] / total if total > 0 else 0
            
            if fail_rate > 0.3 and hint_data["best"] == selector:
                # Find next best selector
                new_best = self._find_next_best(hint_data["selectors"])
                hint_data["best"] = new_best
                print(f"\n⚠️ SELECTOR DEMOTED (high failure rate)")
                print(f"   Domain: {domain}")
                print(f"   Hint: {hint}")
                print(f"   Demoted: {selector} (fail rate: {fail_rate:.1%})")
                print(f"   New Best: {new_best or 'None'}\n")
        
        # Save updated data
        self._save_site(domain, site_data)
    
    def _find_next_best(self, selectors: dict) -> Optional[str]:
        """
        Find next best selector based on success rate and response time.
        
        Args:
            selectors: Dictionary of selector stats
            
        Returns:
            Best selector or None
        """
        best_selector = None
        best_score = 0
        
        for selector, stats in selectors.items():
            total = stats["success"] + stats["fail"]
            if total == 0:
                continue
            
            success_rate = stats["success"] / total
            response_time = stats.get("avg_response_time", 1.0)
            
            # Score: success rate / response time (higher is better)
            score = success_rate / (response_time + 0.1) if response_time else success_rate
            
            if score > best_score:
                best_score = score
                best_selector = selector
        
        return best_selector
    
    def get_llm_context(
        self,
        url: str,
        tool: str = None
    ) -> dict:
        """
        Get minimal context for LLM (token optimization).
        Only sends relevant selectors for current domain + tool.
        
        Args:
            url: Target URL
            tool: Tool name (optional filter)
            
        Returns:
            Compact context dict
        """
        domain = self._extract_domain(url)
        
        # Load site data
        site_data = self._load_site(domain)
        
        # Filter by tool if specified
        if tool:
            site_data = {tool: site_data.get(tool, {})}
        
        # Build compact context (only "best" selectors)
        compact = {}
        for tool_name, tool_data in site_data.items():
            compact[tool_name] = {}
            for hint, hint_data in tool_data.items():
                best = hint_data.get("best")
                if best:
                    compact[tool_name][hint] = best
        
        # Fallback to generic if empty
        if not compact:
            if tool:
                generic_tool = self.generic.get(tool, {})
                compact[tool] = {}
                for hint, data in generic_tool.items():
                    best = data.get("best")
                    if best and isinstance(best, str):
                        compact[tool][hint] = best
            else:
                compact = {}
                for tool_name, tool_data in self.generic.items():
                    tool_dict: Dict[str, str] = {}
                    for hint, data in tool_data.items():
                        best = data.get("best")
                        if best and isinstance(best, str):
                            tool_dict[hint] = best
                    if tool_dict:
                        compact[tool_name] = tool_dict
        
        return compact
    
    def get_stats(self, domain: str = None) -> dict:
        """
        Get statistics about selector cache.
        
        Args:
            domain: Optional domain to get stats for
            
        Returns:
            Statistics dictionary
        """
        if domain:
            site_data = self._load_site(domain)
            return {
                "domain": domain,
                "tools": list(site_data.keys()),
                "hints_count": sum(len(tool_data) for tool_data in site_data.values())
            }
        else:
            # Global stats
            cache_files = list(self.cache_dir.glob("*.json"))
            return {
                "total_sites": len(cache_files),
                "loaded_sites": len(self.loaded_sites),
                "cache_dir": str(self.cache_dir),
                "sites": [f.stem for f in cache_files]
            }
    
    def get_all_hints(self) -> List[str]:
        """
        Backward compatibility: Get all available selector hints.
        
        Returns:
            List of hint names from generic fallbacks
        """
        hints = []
        for tool_data in self.generic.values():
            hints.extend(tool_data.keys())
        return list(set(hints))  # Remove duplicates
    
    # ===== NEW TREE-BASED METHODS =====
    
    def get_page_elements(self, domain: str, path: str = "/") -> List[Dict[str, Any]]:
        """
        Get interactive elements for a specific page.
        
        Args:
            domain: Domain name
            path: Page path (default: "/")
            
        Returns:
            List of interactive elements with attributes
        """
        site_data = self._load_site(domain)
        pages = site_data.get("pages", {})
        page_data = pages.get(path, {})
        return page_data.get("interactive_elements", [])
    
    def save_page_elements(
        self, 
        domain: str, 
        path: str,
        url: str,
        elements: List[Dict[str, Any]]
    ):
        """
        Save interactive elements for a specific page.
        
        Args:
            domain: Domain name
            path: Page path
            url: Full page URL
            elements: List of interactive elements
        """
        site_data = self._load_site(domain)
        
        # Ensure pages structure exists
        if "pages" not in site_data:
            site_data["pages"] = {}
        
        # Create or update page entry
        if path not in site_data["pages"]:
            site_data["pages"][path] = {
                "url": url,
                "visited_at": time.time(),
                "interactive_elements": [],
                "action_map": {},
                "children": []
            }
        
        # Update page data
        page_data = site_data["pages"][path]
        page_data["interactive_elements"] = elements
        page_data["visited_at"] = time.time()
        page_data["url"] = url
        
        # Build action map from elements
        for element in elements:
            # Try to infer semantic name from element attributes
            semantic_names = self._infer_semantic_names(element)
            for name in semantic_names:
                page_data["action_map"][name] = element.get("selector", "")
        
        self._save_site(domain, site_data)
        print(f"[SELECTOR_MAP] Saved {len(elements)} elements for {domain}{path}")
    
    def _infer_semantic_names(self, element: Dict[str, Any]) -> List[str]:
        """Infer semantic names from element attributes."""
        names = []
        
        # Use ID as semantic name
        if element.get("id"):
            names.append(element["id"])
        
        # Use name attribute
        if element.get("name"):
            names.append(element["name"])
        
        # Infer from type and placeholder
        elem_type = element.get("type", "")
        placeholder = element.get("placeholder", "")
        
        if elem_type == "search" or "search" in placeholder.lower():
            names.append("search_input")
        
        # Infer from text content
        text = element.get("text", "").lower()
        if "login" in text or "sign in" in text:
            names.append("login_button")
        elif "signup" in text or "sign up" in text or "register" in text:
            names.append("signup_button")
        
        return names
    
    def get_page_action_selector(
        self, 
        domain: str, 
        path: str, 
        action: str
    ) -> Optional[str]:
        """
        Get selector for a specific action on a specific page.
        O(1) lookup using action_map.
        
        Args:
            domain: Domain name
            path: Page path
            action: Action hint
            
        Returns:
            CSS selector or None
        """
        site_data = self._load_site(domain)
        pages = site_data.get("pages", {})
        page_data = pages.get(path, {})
        action_map = page_data.get("action_map", {})
        
        selector = action_map.get(action)
        if selector:
            print(f"[SELECTOR_MAP] Found cached action '{action}' for {domain}{path}")
        
        return selector
    
    def save_page_action_selector(
        self,
        domain: str,
        path: str,
        action: str,
        selector: str
    ):
        """
        Save action→selector mapping for a specific page.
        
        Args:
            domain: Domain name
            path: Page path
            action: Action hint
            selector: CSS selector
        """
        site_data = self._load_site(domain)
        
        if "pages" not in site_data:
            site_data["pages"] = {}
        
        if path not in site_data["pages"]:
            site_data["pages"][path] = {
                "url": f"https://{domain}{path}",
                "visited_at": time.time(),
                "interactive_elements": [],
                "action_map": {},
                "children": []
            }
        
        # Update action map
        site_data["pages"][path]["action_map"][action] = selector
        
        self._save_site(domain, site_data)
        print(f"[SELECTOR_MAP] Cached action '{action}' → '{selector}' for {domain}{path}")
    
    def add_page_link(
        self,
        domain: str,
        parent_path: str,
        child_path: str
    ):
        """
        Track navigation link from parent page to child page.
        Builds incremental site tree.
        
        Args:
            domain: Domain name
            parent_path: Parent page path
            child_path: Child page path
        """
        site_data = self._load_site(domain)
        
        if "pages" not in site_data:
            site_data["pages"] = {}
        
        if parent_path not in site_data["pages"]:
            site_data["pages"][parent_path] = {
                "url": f"https://{domain}{parent_path}",
                "visited_at": time.time(),
                "interactive_elements": [],
                "action_map": {},
                "children": []
            }
        
        # Add child link if not already present
        children = site_data["pages"][parent_path]["children"]
        if child_path not in children:
            children.append(child_path)
            self._save_site(domain, site_data)
            print(f"[SELECTOR_MAP] Added link: {domain}{parent_path} → {child_path}")
    
    def get_page_tree(self, domain: str) -> Dict[str, Any]:
        """
        Get full page tree for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Page tree structure
        """
        site_data = self._load_site(domain)
        return site_data.get("pages", {})


# Global instance
_selector_map = None


def get_selector_map() -> SelectorMap:
    """
    Get global selector map instance (singleton).
    
    Returns:
        SelectorMap instance
    """
    global _selector_map
    if _selector_map is None:
        _selector_map = SelectorMap()
    return _selector_map
