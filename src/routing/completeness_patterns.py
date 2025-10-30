"""
Completeness Patterns - Generic patterns for detecting items in results.

Works for ANY content type - books, songs, restaurants, movies, etc.
No hardcoded content-specific logic!

Architecture:
- Generic regex patterns for common list formats
- Confidence-based pattern selection
- Automatic pattern matching and item extraction

Example:
    from src.routing.completeness_patterns import detect_items
    
    content = "1. Harry Potter\n2. Lord of the Rings\n3. The Hobbit"
    items = detect_items(content)
    # Returns: ["Harry Potter", "Lord of the Rings", "The Hobbit"]
"""

from typing import List, Dict, Any, Optional
import re


# Generic patterns that work for any content type
COMPLETENESS_PATTERNS = {
    "numbered_list": {
        "patterns": [
            r'^\s*(\d+)[\.\)]\s+(.+?)(?:\n|$)',      # "1. Item" or "1) Item"
            r'^\s*#(\d+)[\.\s]+(.+?)(?:\n|$)',       # "#1. Item" or "#1 Item"
            r'(\d+)\.\s*([A-Z][^\n]+?)(?:\n|$)',     # "1. Title" (relaxed)
        ],
        "confidence": 0.9,
        "description": "Numbered list items (e.g., '1. Title', '1) Title')"
    },
    
    "bullet_list": {
        "patterns": [
            r'^\s*[-•*]\s+(.+?)(?:\n|$)',            # "- Item" or "• Item" or "* Item"
            r'^\s*[▪▫]\s+(.+?)(?:\n|$)',             # "▪ Item" or "▫ Item"
            r'^\s*○\s+(.+?)(?:\n|$)',                # "○ Item"
        ],
        "confidence": 0.8,
        "description": "Bullet point items"
    },
    
    "title_with_creator": {
        "patterns": [
            r'([A-Z][^:\n]+?)\s+by\s+([A-Z][a-z]+[^\n]*?)(?:\n|$)',     # "Title by Author"
            r'([A-Z][^:\n]+?)\s+-\s+([A-Z][a-z]+[^\n]*?)(?:\n|$)',      # "Title - Artist"
            r'([A-Z][^:\n]+?)\s+\((\d{4})\)',                            # "Title (2024)"
            r'([A-Z][^:\n]+?)\s+–\s+([A-Z][a-z]+[^\n]*?)(?:\n|$)',      # "Title – Creator" (em dash)
        ],
        "confidence": 0.85,
        "description": "Items with creator or year (e.g., 'Title by Author', 'Song - Artist')"
    },
    
    "table_row": {
        "patterns": [
            r'\|([^\|]+)\|([^\|]+)\|',                                    # "| Col1 | Col2 |"
            r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>',                        # HTML table rows
        ],
        "confidence": 0.95,
        "description": "Table rows (Markdown or HTML)"
    },
    
    "heading_with_number": {
        "patterns": [
            r'##?\s*(\d+)[\.\s]+(.+?)(?:\n|$)',                          # "## 1. Title" or "# 1 Title"
            r'<h[1-6]>\s*(\d+)[\.\s]*([^<]+)</h[1-6]>',                 # HTML headings
        ],
        "confidence": 0.88,
        "description": "Headings with numbers (Markdown or HTML)"
    },
    
    "json_list": {
        "patterns": [
            r'"(?:title|name|item)":\s*"([^"]+)"',                       # JSON properties
            r'\{\s*"[^"]+"\s*:\s*"([^"]+)"',                             # Simple JSON objects
        ],
        "confidence": 1.0,
        "description": "JSON list items"
    }
}


def detect_items(
    content: str,
    pattern_type: Optional[str] = None,
    min_length: int = 3
) -> List[str]:
    """
    Detect items in content using generic patterns.
    Tries all patterns and returns best match by confidence.
    
    Args:
        content: Text content to analyze
        pattern_type: Specific pattern to use, or None for auto-detect
        min_length: Minimum item length to consider valid
    
    Returns:
        List of detected items (unique, ordered by appearance)
    
    Example:
        >>> content = "1. Harry Potter\n2. Lord of the Rings\n3. The Hobbit"
        >>> items = detect_items(content)
        >>> print(items)
        ['Harry Potter', 'Lord of the Rings', 'The Hobbit']
    """
    if not content or not isinstance(content, str):
        return []
    
    # If specific pattern type requested, use only that
    if pattern_type and pattern_type in COMPLETENESS_PATTERNS:
        patterns_to_try = {pattern_type: COMPLETENESS_PATTERNS[pattern_type]}
    else:
        # Try all patterns
        patterns_to_try = COMPLETENESS_PATTERNS
    
    best_items = []
    best_confidence = 0
    best_pattern_type = None
    
    for current_pattern_type, pattern_config in patterns_to_try.items():
        items = []
        items_order = []  # Track order of appearance
        
        for pattern in pattern_config["patterns"]:
            try:
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                
                if matches:
                    for match in matches:
                        # Handle tuples from capture groups
                        if isinstance(match, tuple):
                            # Try to get the most meaningful part
                            # Usually the last non-empty group
                            item = None
                            for part in reversed(match):
                                if part and part.strip():
                                    item = part.strip()
                                    break
                            if not item:
                                item = match[0].strip() if match[0] else ""
                        else:
                            item = match.strip()
                        
                        # Validate item
                        if item and len(item) >= min_length:
                            # Clean up item
                            item = clean_item_text(item)
                            
                            # Avoid duplicates while preserving order
                            if item not in items:
                                items.append(item)
                                items_order.append(item)
            
            except re.error as e:
                print(f"[PATTERNS] Regex error with pattern '{pattern}': {e}")
                continue
        
        # Check if this pattern found items and has better confidence
        if items and pattern_config["confidence"] > best_confidence:
            best_items = items
            best_confidence = pattern_config["confidence"]
            best_pattern_type = current_pattern_type
    
    if best_items:
        print(f"[PATTERNS] Found {len(best_items)} items using '{best_pattern_type}' pattern (confidence: {best_confidence})")
    else:
        print(f"[PATTERNS] No items detected in content")
    
    return best_items


def clean_item_text(text: str) -> str:
    """
    Clean extracted item text.
    
    Removes:
    - Extra whitespace
    - HTML tags
    - Special markers
    - Trailing punctuation
    
    Args:
        text: Raw item text
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    
    # Remove special markers (e.g., "___", ">>", "<<")
    text = re.sub(r'_{3,}|>{2,}|<{2,}', '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    # Remove trailing punctuation (but keep internal)
    text = text.rstrip('.,;:!?')
    
    return text.strip()


def count_items(content: str, pattern_type: Optional[str] = None) -> int:
    """
    Count items in content without extracting them.
    Faster than detect_items() when you only need the count.
    
    Args:
        content: Text content to analyze
        pattern_type: Specific pattern to use, or None for auto-detect
    
    Returns:
        Number of items found
    
    Example:
        >>> content = "1. Item A\n2. Item B\n3. Item C"
        >>> count = count_items(content)
        >>> print(count)
        3
    """
    items = detect_items(content, pattern_type)
    return len(items)


def get_pattern_info(pattern_type: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific pattern type.
    
    Args:
        pattern_type: Pattern type identifier
    
    Returns:
        Pattern configuration dict or None
    """
    return COMPLETENESS_PATTERNS.get(pattern_type)


def list_available_patterns() -> List[str]:
    """
    List all available pattern types.
    
    Returns:
        List of pattern type identifiers
    """
    return list(COMPLETENESS_PATTERNS.keys())


def analyze_content_structure(content: str) -> Dict[str, Any]:
    """
    Analyze content to determine best pattern match.
    Returns detailed information about what patterns matched.
    
    Args:
        content: Text content to analyze
    
    Returns:
        Dictionary with analysis results
    
    Example:
        >>> analysis = analyze_content_structure(content)
        >>> print(analysis)
        {
            "best_pattern": "numbered_list",
            "confidence": 0.9,
            "item_count": 10,
            "matches_per_pattern": {...}
        }
    """
    results = {
        "best_pattern": None,
        "confidence": 0,
        "item_count": 0,
        "matches_per_pattern": {}
    }
    
    for pattern_type, pattern_config in COMPLETENESS_PATTERNS.items():
        items = detect_items(content, pattern_type)
        count = len(items)
        
        results["matches_per_pattern"][pattern_type] = {
            "count": count,
            "confidence": pattern_config["confidence"],
            "description": pattern_config["description"]
        }
        
        # Update best if this is better
        if count > 0 and pattern_config["confidence"] > results["confidence"]:
            results["best_pattern"] = pattern_type
            results["confidence"] = pattern_config["confidence"]
            results["item_count"] = count
    
    return results


def extract_with_context(
    content: str,
    pattern_type: Optional[str] = None,
    context_lines: int = 1
) -> List[Dict[str, Any]]:
    """
    Extract items with surrounding context.
    Useful for understanding what was found.
    
    Args:
        content: Text content to analyze
        pattern_type: Specific pattern to use, or None for auto-detect
        context_lines: Number of lines before/after to include
    
    Returns:
        List of dicts with item and context
    
    Example:
        >>> results = extract_with_context(content, context_lines=1)
        >>> for r in results:
        ...     print(f"{r['item']}: {r['context']}")
    """
    items = detect_items(content, pattern_type)
    lines = content.split('\n')
    
    results = []
    for item in items:
        # Find line containing this item
        for i, line in enumerate(lines):
            if item in line:
                # Get context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = '\n'.join(lines[start:end])
                
                results.append({
                    "item": item,
                    "line_number": i + 1,
                    "context": context
                })
                break
    
    return results
