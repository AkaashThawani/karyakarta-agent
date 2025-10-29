"""
Global Selector Map

Manages a global map of semantic selector hints to CSS selectors.
Learns and improves over time by promoting working selectors.
"""

import json
import os
from typing import List, Optional
from pathlib import Path


class SelectorMap:
    """
    Manages a global map of selector hints to CSS selectors.
    
    This allows the LLM to use semantic hints like "search_input"
    instead of raw CSS selectors, with automatic fallback and learning.
    """
    
    def __init__(self, cache_file: str = "selector_map.json"):
        """
        Initialize selector map.
        
        Args:
            cache_file: Path to cache file (relative to project root)
        """
        self.cache_file = Path(__file__).parent.parent.parent / cache_file
        self.map = self._load_map()
    
    def _load_map(self) -> dict:
        """
        Load selector map from file or create default.
        
        Returns:
            Selector map dictionary
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[SELECTOR_MAP] Error loading map: {e}")
                return self._get_default_map()
        else:
            return self._get_default_map()
    
    def _get_default_map(self) -> dict:
        """
        Get default selector map with common patterns.
        
        Returns:
            Default selector map
        """
        return {
            "search_input": [
                "input[name='search_query']",  # YouTube
                "input[name='q']",  # Google
                "textarea[name='q']",  # Google (new UI)
                "input[data-testid='search-input']",  # Spotify
                "input[placeholder*='search' i]",
                "input[aria-label*='search' i]",
                "input[type='search']",
                "input[name*='search' i]"
            ],
            "login_button": [
                "button[data-testid='login-button']",
                "button:has-text('Log in')",
                "button:has-text('Sign in')",
                "a:has-text('Log in')",
                "a:has-text('Sign in')",
                "button[aria-label*='login' i]",
                "a[href*='login']"
            ],
            "submit_button": [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Go')",
                "button:has-text('Search')"
            ],
            "email_field": [
                "input[type='email']",
                "input[name='email']",
                "input[name*='email' i]",
                "input[placeholder*='email' i]",
                "input[aria-label*='email' i]"
            ],
            "password_field": [
                "input[type='password']",
                "input[name='password']",
                "input[name*='password' i]",
                "input[placeholder*='password' i]",
                "input[aria-label*='password' i]"
            ],
            "username_field": [
                "input[name='username']",
                "input[name='user']",
                "input[name*='username' i]",
                "input[placeholder*='username' i]",
                "input[aria-label*='username' i]"
            ]
        }
    
    def _save_map(self) -> None:
        """Save selector map to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.map, f, indent=2)
            print(f"[SELECTOR_MAP] Saved to {self.cache_file}")
        except Exception as e:
            print(f"[SELECTOR_MAP] Error saving map: {e}")
    
    def get_selectors(self, hint: str) -> List[str]:
        """
        Get list of selectors for a hint.
        
        Args:
            hint: Semantic selector hint (e.g., "search_input")
            
        Returns:
            List of CSS selectors to try, in priority order
        """
        selectors = self.map.get(hint, [])
        print(f"[SELECTOR_MAP] Retrieved {len(selectors)} selectors for hint '{hint}'")
        return selectors
    
    def add_selector(self, hint: str, selector: str) -> None:
        """
        Add a new working selector to a hint.
        
        Args:
            hint: Semantic selector hint
            selector: CSS selector that worked
        """
        if hint not in self.map:
            self.map[hint] = []
        
        if selector not in self.map[hint]:
            # Add to front of list (highest priority)
            self.map[hint].insert(0, selector)
            self._save_map()
            print(f"[SELECTOR_MAP] Added new selector '{selector}' for hint '{hint}'")
    
    def promote_selector(self, hint: str, selector: str) -> None:
        """
        Promote a working selector to front of list (learning).
        
        Args:
            hint: Semantic selector hint
            selector: CSS selector that worked
        """
        if hint in self.map and selector in self.map[hint]:
            # Move to front if not already there
            if self.map[hint][0] != selector:
                self.map[hint].remove(selector)
                self.map[hint].insert(0, selector)
                self._save_map()
                print(f"[SELECTOR_MAP] Promoted selector '{selector}' for hint '{hint}'")
    
    def get_all_hints(self) -> List[str]:
        """
        Get list of all available selector hints.
        
        Returns:
            List of hint names
        """
        return list(self.map.keys())


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
