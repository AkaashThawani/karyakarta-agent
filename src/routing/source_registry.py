"""
Dynamic Source Registry - Self-Learning Content Source Management

A self-improving registry that learns:
- New aliases from user queries
- New keywords from extracted fields  
- Field mappings from discoveries
- Category similarities for auto-merging
- Source reliability from success rates

Architecture:
- Category-based organization with canonical names
- Alias system for flexible matching
- Dynamic learning from every query
- No duplicates - automatic deduplication
- Parallel-safe with file-based persistence

Example:
    from src.routing.source_registry import DynamicSourceRegistry
    
    registry = DynamicSourceRegistry()
    
    # Get sources (learns from query)
    sources = registry.get_sources_for_category("top songs")
    
    # After extraction, update registry
    registry.process_successful_extraction(
        user_query="top songs",
        category="music_charts",
        domain="spotify.com",
        extracted_fields=["song", "artist", "rank"]
    )
"""

from typing import List, Dict, Any, Optional, Set
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse


class DynamicSourceRegistry:
    """
    Self-learning source registry with category management.
    """
    
    def __init__(self, cache_dir: str = "source_cache"):
        """Initialize registry with cache directory."""
        self.cache_dir = Path(__file__).parent.parent.parent / cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        
        self.cache_file = self.cache_dir / "category_sources.json"
        self.categories: Dict[str, Any] = {}
        self.category_mappings: Dict[str, str] = {}
        
        # Load existing data
        self.load()
        
        # Initialize with defaults if empty
        if not self.categories:
            self._initialize_defaults()
        
        print(f"[REGISTRY] Initialized with {len(self.categories)} categories")
    
    def _initialize_defaults(self):
        """Initialize with default categories."""
        self.categories = {
            "music_charts": {
                "canonical_name": "music_charts",
                "description": "Top music charts and song rankings",
                "aliases": ["songs", "top_songs", "song_charts", "music", "hit_songs"],
                "keywords": ["song", "artist", "music", "chart", "album", "track"],
                "websites": [
                    {
                        "domain": "spotify.com",
                        "url": "https://charts.spotify.com/",
                        "fields": ["song", "artist", "rank"],
                        "priority": 1,
                        "reliability": 0.95,
                        "added_at": datetime.now().isoformat()
                    },
                    {
                        "domain": "billboard.com",
                        "url": "https://www.billboard.com/charts/hot-100/",
                        "fields": ["song", "artist", "producer", "release_date"],
                        "priority": 2,
                        "reliability": 0.90,
                        "added_at": datetime.now().isoformat()
                    }
                ],
                "required_fields": ["song", "artist"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            },
            "books": {
                "canonical_name": "books",
                "description": "Book rankings and bestsellers",
                "aliases": ["book", "bestsellers", "reading"],
                "keywords": ["book", "author", "publisher", "isbn"],
                "websites": [
                    {
                        "domain": "nytimes.com",
                        "url": "https://www.nytimes.com/books/best-sellers/",
                        "fields": ["title", "author", "rank"],
                        "priority": 1,
                        "reliability": 0.98,
                        "added_at": datetime.now().isoformat()
                    }
                ],
                "required_fields": ["title", "author"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }
        
        # Build initial mappings
        self._rebuild_mappings()
        
        self.save()
    
    def _rebuild_mappings(self):
        """Rebuild category mappings from aliases."""
        self.category_mappings = {}
        for canonical, data in self.categories.items():
            for alias in data["aliases"]:
                self.category_mappings[alias] = canonical
    
    def load(self):
        """Load registry from cache file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.categories = data.get("categories", {})
                    self.category_mappings = data.get("category_mappings", {})
                print(f"[REGISTRY] Loaded {len(self.categories)} categories from cache")
            except Exception as e:
                print(f"[REGISTRY] Error loading cache: {e}")
    
    def save(self):
        """Save registry to cache file."""
        try:
            data = {
                "categories": self.categories,
                "category_mappings": self.category_mappings,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"[REGISTRY] Saved {len(self.categories)} categories to cache")
        except Exception as e:
            print(f"[REGISTRY] Error saving: {e}")
    
    # ===== CATEGORY NORMALIZATION =====
    
    def normalize_category(self, user_query: str) -> str:
        """
        Convert user query to canonical category name.
        
        Args:
            user_query: Raw user query
            
        Returns:
            Canonical category name
        """
        query_lower = user_query.lower()
        
        # Check direct mappings first
        for alias, canonical in self.category_mappings.items():
            if alias in query_lower:
                return canonical
        
        # Check keywords
        best_match = None
        best_score = 0
        
        for canonical, data in self.categories.items():
            score = 0
            
            # Score by keyword matches
            for keyword in data["keywords"]:
                if keyword in query_lower:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = canonical
        
        if best_match and best_score >= 2:
            return best_match
        
        # Not found - return query as new category
        return self._create_category_name(query_lower)
    
    def _create_category_name(self, query: str) -> str:
        """Create category name from query."""
        # Extract key words - extensive stop words list
        stop_words = {
            "find", "get", "show", "me", "the", "top", "best", "list", "of",
            "can", "you", "what", "are", "is", "for", "with", "from", "about",
            "give", "tell", "search", "look", "want", "need", "please", "a", "an"
        }
        words = [w for w in query.lower().split() if w not in stop_words and len(w) > 2]
        
        # Take first 2-3 meaningful words
        category_name = "_".join(words[:2]) if words else "general"
        return category_name
    
    # ===== SOURCE MANAGEMENT =====
    
    def get_sources_for_category(self, category_query: str) -> List[Dict[str, Any]]:
        """
        Get sources for a category (with normalization).
        
        Args:
            category_query: User's category query
            
        Returns:
            List of sources sorted by priority
        """
        canonical = self.normalize_category(category_query)
        
        if canonical not in self.categories:
            print(f"[REGISTRY] Category '{canonical}' not found")
            return []
        
        websites = self.categories[canonical]["websites"]
        
        # Sort by priority (lower number = higher priority)
        sorted_websites = sorted(websites, key=lambda x: x.get("priority", 99))
        
        print(f"[REGISTRY] Found {len(sorted_websites)} sources for '{canonical}'")
        return sorted_websites
    
    def add_source_to_category(
        self,
        category_query: str,
        domain: str,
        url: str,
        fields: List[str],
        priority: Optional[int] = None
    ):
        """
        Add source to category (with deduplication).
        
        Args:
            category_query: Category name or query
            domain: Domain name
            url: Source URL
            fields: Fields available from this source
            priority: Priority (lower = higher priority)
        """
        canonical = self.normalize_category(category_query)
        
        # Ensure category exists
        if canonical not in self.categories:
            self._create_category(canonical, category_query)
        
        # Check if source already exists
        if self.source_exists(canonical, domain):
            print(f"[REGISTRY] Source {domain} already in {canonical}, updating...")
            self.update_source_fields(canonical, domain, fields)
            return
        
        # Calculate priority if not provided
        if priority is None:
            existing_sources = len(self.categories[canonical]["websites"])
            priority = existing_sources + 1
        
        # Add new source
        self.categories[canonical]["websites"].append({
            "domain": domain,
            "url": url,
            "fields": fields,
            "priority": priority,
            "reliability": 0.5,  # Initial low reliability
            "success_count": 0,
            "fail_count": 0,
            "added_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        })
        
        self.categories[canonical]["updated_at"] = datetime.now().isoformat()
        
        print(f"[REGISTRY] Added {domain} to {canonical}")
        self.save()
    
    def source_exists(self, category: str, domain: str) -> bool:
        """Check if source already exists in category."""
        if category not in self.categories:
            return False
        
        websites = self.categories[category]["websites"]
        return any(site["domain"] == domain for site in websites)
    
    def update_source_fields(self, category: str, domain: str, new_fields: List[str]):
        """Update fields for an existing source."""
        for source in self.categories[category]["websites"]:
            if source["domain"] == domain:
                existing_fields = set(source["fields"])
                merged_fields = list(existing_fields | set(new_fields))
                
                if len(merged_fields) > len(existing_fields):
                    source["fields"] = merged_fields
                    source["last_updated"] = datetime.now().isoformat()
                    print(f"[REGISTRY] Updated {domain} fields: {merged_fields}")
                    self.save()
                
                break
    
    def update_reliability(self, category: str, domain: str, success: bool):
        """Update reliability score based on success/failure."""
        canonical = self.normalize_category(category)
        
        for source in self.categories[canonical]["websites"]:
            if source["domain"] == domain:
                if success:
                    source["success_count"] = source.get("success_count", 0) + 1
                else:
                    source["fail_count"] = source.get("fail_count", 0) + 1
                
                # Calculate reliability
                total = source["success_count"] + source["fail_count"]
                if total > 0:
                    source["reliability"] = source["success_count"] / total
                
                source["last_updated"] = datetime.now().isoformat()
                
                print(f"[REGISTRY] Updated {domain} reliability: {source['reliability']:.2f}")
                self.save()
                break
    
    # ===== DYNAMIC LEARNING =====
    
    def learn_alias_from_query(self, user_query: str, matched_category: str):
        """Learn new alias from successful query."""
        query_lower = user_query.lower()
        
        # Extract potential alias
        stop_words = {"find", "get", "show", "me", "the", "top", "best", "a", "an"}
        words = [w for w in query_lower.split() if w not in stop_words]
        potential_alias = " ".join(words[:3])  # Max 3 words
        
        # Validate
        if len(potential_alias) < 3:
            return
        
        if potential_alias in self.categories[matched_category]["aliases"]:
            return
        
        # Check for conflicts
        for alias in self.category_mappings:
            if alias == potential_alias:
                return  # Already mapped to different category
        
        # Add alias
        self.categories[matched_category]["aliases"].append(potential_alias)
        self.category_mappings[potential_alias] = matched_category
        
        print(f"[REGISTRY] ✨ Learned alias: '{potential_alias}' → {matched_category}")
        self.save()
    
    def learn_keywords_from_fields(self, category: str, extracted_fields: List[str]):
        """Learn keywords from extracted field names."""
        current_keywords = set(self.categories[category]["keywords"])
        new_keywords = []
        
        for field in extracted_fields:
            # Normalize field name
            normalized = field.lower().replace("_", " ")
            
            if normalized not in current_keywords and len(normalized) > 2:
                self.categories[category]["keywords"].append(normalized)
                new_keywords.append(normalized)
        
        if new_keywords:
            print(f"[REGISTRY] ✨ Learned keywords: {new_keywords} for {category}")
            self.save()
    
    def process_successful_extraction(
        self,
        user_query: str,
        category: str,
        domain: str,
        url: str,
        extracted_fields: List[str],
        extracted_data: Optional[Dict[str, Any]] = None
    ):
        """
        Process successful extraction - learn everything!
        
        Args:
            user_query: Original user query
            category: Matched category
            domain: Source domain
            url: Source URL
            extracted_fields: Fields that were extracted
            extracted_data: Actual data (optional)
        """
        canonical = self.normalize_category(category)
        
        print(f"\n{'='*60}")
        print(f"📚 LEARNING FROM SUCCESSFUL EXTRACTION")
        print(f"{'='*60}")
        print(f"Query: {user_query}")
        print(f"Category: {canonical}")
        print(f"Source: {domain}")
        print(f"Fields: {extracted_fields}")
        
        # 1. Learn alias
        self.learn_alias_from_query(user_query, canonical)
        
        # 2. Learn keywords
        self.learn_keywords_from_fields(canonical, extracted_fields)
        
        # 3. Update source fields
        self.update_source_fields(canonical, domain, extracted_fields)
        
        # 4. Update reliability
        self.update_reliability(canonical, domain, success=True)
        
        print(f"{'='*60}\n")
    
    def _create_category(self, canonical_name: str, original_query: str):
        """Create new category from query."""
        # Extract initial keywords
        words = [w for w in original_query.lower().split() if len(w) > 2]
        
        self.categories[canonical_name] = {
            "canonical_name": canonical_name,
            "description": f"Category for {original_query}",
            "aliases": [canonical_name],
            "keywords": words[:5],  # Initial keywords
            "websites": [],
            "required_fields": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        print(f"[REGISTRY] ✨ Created new category: {canonical_name}")
        self.save()
    
    # ===== CATEGORY SIMILARITY & MERGING =====
    
    def calculate_similarity(self, cat1: str, cat2: str) -> float:
        """Calculate similarity between two categories."""
        if cat1 not in self.categories or cat2 not in self.categories:
            return 0.0
        
        data1 = self.categories[cat1]
        data2 = self.categories[cat2]
        
        # Compare keywords
        keywords1 = set(data1["keywords"])
        keywords2 = set(data2["keywords"])
        
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        keyword_similarity = intersection / union if union > 0 else 0
        
        # Compare websites (same sources = likely same category)
        domains1 = {site["domain"] for site in data1["websites"]}
        domains2 = {site["domain"] for site in data2["websites"]}
        
        if domains1 and domains2:
            domain_overlap = len(domains1 & domains2) / max(len(domains1), len(domains2))
        else:
            domain_overlap = 0
        
        # Weighted average
        return (keyword_similarity * 0.6) + (domain_overlap * 0.4)
    
    def merge_similar_categories(self, threshold: float = 0.8):
        """Detect and merge similar categories."""
        categories = list(self.categories.keys())
        merged = []
        
        for i, cat1 in enumerate(categories):
            if cat1 in merged:
                continue
            
            for cat2 in categories[i+1:]:
                if cat2 in merged:
                    continue
                
                similarity = self.calculate_similarity(cat1, cat2)
                
                if similarity > threshold:
                    print(f"[REGISTRY] 🔄 Merging {cat2} into {cat1} (similarity: {similarity:.2f})")
                    self._merge_categories(cat1, cat2)
                    merged.append(cat2)
        
        if merged:
            self.save()
    
    def _merge_categories(self, keep: str, remove: str):
        """Merge remove into keep."""
        # Merge aliases
        self.categories[keep]["aliases"].extend(
            self.categories[remove]["aliases"]
        )
        self.categories[keep]["aliases"] = list(set(self.categories[keep]["aliases"]))
        
        # Merge keywords
        self.categories[keep]["keywords"].extend(
            self.categories[remove]["keywords"]
        )
        self.categories[keep]["keywords"] = list(set(self.categories[keep]["keywords"]))
        
        # Merge websites (deduplicate by domain)
        existing_domains = {site["domain"] for site in self.categories[keep]["websites"]}
        
        for site in self.categories[remove]["websites"]:
            if site["domain"] not in existing_domains:
                self.categories[keep]["websites"].append(site)
        
        # Update mappings
        for alias in self.categories[remove]["aliases"]:
            self.category_mappings[alias] = keep
        
        # Remove old category
        del self.categories[remove]
        
        print(f"[REGISTRY] ✅ Merged {remove} into {keep}")
    
    # ===== UTILITY METHODS =====
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_sources = sum(len(cat["websites"]) for cat in self.categories.values())
        total_aliases = sum(len(cat["aliases"]) for cat in self.categories.values())
        
        return {
            "total_categories": len(self.categories),
            "total_sources": total_sources,
            "total_aliases": total_aliases,
            "categories": list(self.categories.keys()),
            "cache_file": str(self.cache_file)
        }


# Global instance
_registry: Optional[DynamicSourceRegistry] = None


def get_source_registry() -> DynamicSourceRegistry:
    """Get global source registry instance (singleton)."""
    global _registry
    if _registry is None:
        _registry = DynamicSourceRegistry()
    return _registry
