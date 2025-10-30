"""
Helper Utilities - Thin wrappers around open-source libraries

This module provides convenient wrappers around third-party libraries
for common operations like validation, formatting, retry logic, and caching.

For detailed library usage, see: docs/LIBRARY_USAGE_GUIDE.md
"""

from typing import Any, Callable, Optional, TypeVar, List
from datetime import datetime
import re
import validators
import humanize
from tenacity import retry, stop_after_attempt, wait_exponential
from cachetools import TTLCache
from bs4 import BeautifulSoup
import tiktoken

T = TypeVar('T')

# ============================================================================
# Validation Helpers (using 'validators' library)
# ============================================================================

def validate_url(url: str, require_https: bool = False) -> bool:
    """
    Validate if string is a valid URL.
    
    Args:
        url: URL to validate
        require_https: If True, only HTTPS URLs are valid
        
    Returns:
        bool: True if valid URL
    """
    if not validators.url(url):
        return False
    
    if require_https and not url.startswith('https://'):
        return False
    
    return True


def validate_email(email: str) -> bool:
    """Validate if string is a valid email address."""
    return bool(validators.email(email))


# ============================================================================
# Formatting Helpers (using 'humanize' library)
# ============================================================================

def format_file_size(bytes_count: int) -> str:
    """Format bytes to human-readable size (e.g., '1.5 MB')."""
    return humanize.naturalsize(bytes_count)


def format_timestamp(dt: datetime, relative: bool = False) -> str:
    """
    Format datetime to readable string.
    
    Args:
        dt: Datetime to format
        relative: If True, return relative time (e.g., '2 hours ago')
        
    Returns:
        Formatted string
    """
    if relative:
        return humanize.naturaltime(dt)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_number(num: int, short: bool = False) -> str:
    """
    Format large numbers.
    
    Args:
        num: Number to format
        short: If True, use short form (e.g., '1.5M')
        
    Returns:
        Formatted string
    """
    if short:
        return humanize.intword(num)
    return humanize.intcomma(num)


# ============================================================================
# Retry Decorator (using 'tenacity' library)
# ============================================================================

def retry_on_failure(
    max_attempts: int = 3,
    min_wait: int = 1,
    max_wait: int = 10
) -> Callable:
    """
    Decorator to retry function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        
    Returns:
        Decorated function
        
    Example:
        @retry_on_failure(max_attempts=3)
        def fetch_data():
            return requests.get(url)
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait)
    )


# ============================================================================
# Caching (using 'cachetools' library)
# ============================================================================

# Global caches for common use cases
_api_cache = TTLCache(maxsize=100, ttl=300)  # 5 minutes
_search_cache = TTLCache(maxsize=50, ttl=600)  # 10 minutes


def get_api_cache() -> TTLCache:
    """Get the global API response cache."""
    return _api_cache


def get_search_cache() -> TTLCache:
    """Get the global search results cache."""
    return _search_cache


# ============================================================================
# Utility Functions
# ============================================================================

def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_get(dictionary: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.
    
    Args:
        dictionary: Dict to search
        *keys: Keys to traverse
        default: Default if not found
        
    Returns:
        Value or default
        
    Example:
        safe_get(data, 'user', 'profile', 'name', default='Unknown')
    """
    result = dictionary
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


# ============================================================================
# Content Compression & Chunking
# ============================================================================

def smart_compress(html: str, max_tokens: int = 1500) -> str:
    """
    Universal content compression with exact token control.
    
    Works for ANY content type (products, events, articles, documentation).
    Uses priority-based extraction and tiktoken for exact token limits.
    
    Strategy:
    1. Remove bloat (scripts, styles, navigation)
    2. Find main content area
    3. Extract with priority: headings → paragraphs → lists → tables
    4. Truncate to exact token limit
    
    Args:
        html: Raw HTML content
        max_tokens: Maximum tokens to return (default 1500 = ~80% cost savings)
        
    Returns:
        Compressed content maintaining context and readability
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # STEP 1: Aggressively remove all non-content elements
    # Remove scripts, styles, and other bloat
    for tag in soup(['script', 'style', 'link', 'meta', 'nav', 'footer', 'header', 
                      'aside', 'iframe', 'noscript', 'svg', 'path', 'use']):
        tag.decompose()
    
    # Remove inline styles and onclick handlers
    for tag in soup.find_all(True):
        if tag.has_attr('style'):
            del tag['style']
        if tag.has_attr('onclick'):
            del tag['onclick']
        if tag.has_attr('onload'):
            del tag['onload']
        # Remove data attributes and IDs/classes for cleaner output
        for attr in ['class', 'id', 'data-*']:
            if tag.has_attr(attr):
                del tag[attr]
    
    # Remove HTML comments
    for comment in soup.findAll(text=lambda text: isinstance(text, str) and '<!--' in text):
        comment.extract()
    
    # Try to find main content area
    main_content = (
        soup.find('main') or 
        soup.find('article') or 
        soup.find(id=re.compile(r'content|main', re.I)) or
        soup.find(class_=re.compile(r'content|main|body', re.I)) or
        soup
    )
    
    # Extract content with priority
    content_parts = []
    
    # Priority 1: Headings (structure and key topics)
    headings = main_content.find_all(['h1', 'h2', 'h3'])[:15]
    for h in headings:
        text = h.get_text(strip=True)
        if text and len(text) < 200:
            # Use markdown-style headers for clarity
            level = int(h.name[1])
            prefix = '#' * level
            content_parts.append(f"{prefix} {text}")
    
    # Priority 2: Paragraphs (main content and descriptions)
    paragraphs = main_content.find_all('p')[:20]
    for p in paragraphs:
        text = p.get_text(strip=True)
        # Skip very short paragraphs (likely navigation or labels)
        if text and len(text) > 40:
            content_parts.append(text)
    
    # Priority 3: Lists (features, specs, options)
    lists = main_content.find_all(['ul', 'ol'])[:8]
    for lst in lists:
        items = lst.find_all('li')[:12]
        for item in items:
            text = item.get_text(strip=True)
            if text and len(text) > 10:
                content_parts.append(f"• {text}")
    
    # Priority 4: Tables (specs, pricing)
    tables = main_content.find_all('table')[:3]
    for table in tables:
        rows = table.find_all('tr')[:10]
        for row in rows:
            cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
            if cells and any(cells):
                content_parts.append(' | '.join(filter(None, cells)))
    
    # Join all parts
    result = '\n\n'.join(content_parts)
    
    # Clean up whitespace
    result = re.sub(r' +', ' ', result)
    result = re.sub(r'\n\n+', '\n\n', result)
    result = result.strip()
    
    # CRITICAL: If extraction failed, use comprehensive fallback
    if not result or len(result.strip()) < 100:
        print(f"[SMART COMPRESS] Structured extraction failed, using comprehensive fallback")
        
        # Fallback strategy: Get ALL visible text content
        # This ensures we never return empty even for unusual page structures
        
        # Try to get body text first
        body = soup.body if soup.body else soup
        
        # Get all text from body, excluding script/style tags which are already removed
        all_text = []
        
        # Method 1: Try get_text() which is more reliable
        body_text = body.get_text(separator=' ', strip=True)
        if body_text and len(body_text) > 100:
            result = body_text
            print(f"[SMART COMPRESS] Fallback method 1 (get_text): {len(result)} characters")
        else:
            # Method 2: Manual extraction
            for element in body.find_all(text=True, recursive=True):
                text = str(element).strip()
                # Skip empty strings and very short text (likely labels/buttons)
                if text and len(text) > 3:
                    # Skip if it's just a number or single word (likely nav/UI)
                    if len(text.split()) > 1 or len(text) > 20:
                        all_text.append(text)
            
            # Join with spacing and clean up
            result = ' '.join(all_text)
            result = re.sub(r' +', ' ', result)  # Collapse multiple spaces
            result = re.sub(r'\n+', '\n', result)  # Collapse multiple newlines
            result = result.strip()
            
            print(f"[SMART COMPRESS] Fallback method 2 (manual): {len(result)} characters")
    
    # Tokenize and truncate to exact limit
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        tokens = encoding.encode(result)
        
        if len(tokens) > max_tokens:
            # Truncate to max tokens
            tokens = tokens[:max_tokens]
            result = encoding.decode(tokens)
            result += "\n\n[Content truncated to token limit]"
        
        # Log token count for monitoring
        print(f"[SMART COMPRESS] Tokens: {min(len(tokens), max_tokens)}/{max_tokens}")
        
    except Exception as e:
        print(f"[SMART COMPRESS] Tiktoken failed: {e}, using char limit")
        # Fallback: use character limit (rough approximation: 1 token ≈ 4 chars)
        char_limit = max_tokens * 4
        if len(result) > char_limit:
            result = result[:char_limit] + "\n\n[Content truncated]"
    
    # Final safety check: never return empty content
    if not result or len(result.strip()) < 50:
        print(f"[SMART COMPRESS] ERROR: Result still empty after all fallbacks!")
        return "[Error: Could not extract any content from page]"
    
    return result


def compress_content(html: str, max_chars: int = 50000) -> str:
    """
    Compress HTML content intelligently for LLM processing.
    
    Strategy:
    1. Extract key content (prices, titles, products)
    2. Remove scripts, styles, navigation
    3. Clean whitespace
    4. Truncate if needed
    
    Args:
        html: Raw HTML content
        max_chars: Maximum characters to return
        
    Returns:
        Compressed text content
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove bloat tags
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
        tag.decompose()
    
    # Remove comments
    for comment in soup.findAll(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
        comment.extract()
    
    # Extract key content with priority
    key_content = []
    
    # Priority 1: Prices (highest priority)
    for price_elem in soup.find_all(class_=re.compile(r'price|cost|amount', re.I)):
        text = price_elem.get_text(strip=True)
        if text and len(text) < 200:  # Avoid long text blocks
            key_content.append(text)  # Removed emoji
    
    # Priority 2: Product titles and headings
    for heading in soup.find_all(['h1', 'h2'])[:5]:  # Reduced from h3, limited to 5
        text = heading.get_text(strip=True)
        if text and len(text) < 200:
            key_content.append(text)  # Removed emoji
    
    # Priority 3: Product info (limited)
    for product in soup.find_all(class_=re.compile(r'product|item|card', re.I))[:3]:  # Limited to 3
        text = product.get_text(strip=True)
        if text and len(text) < 300:  # Reduced from 500
            key_content.append(text)
    
    # Build result (more aggressive)
    if key_content:
        result = '\n\n'.join(key_content[:8])  # Reduced from 20 to 8
    else:
        # Fallback: just get all text
        result = soup.get_text(separator=' ', strip=True)
    
    # Clean whitespace
    result = re.sub(r' +', ' ', result)
    result = re.sub(r'\n\n+', '\n\n', result)
    result = result.strip()
    
    # More aggressive truncation
    if len(result) > max_chars:
        result = result[:max_chars] + "\n[Truncated]"
    
    return result


def chunk_content(content: str, chunk_size: int = 50000, overlap: int = 500) -> List[str]:
    """
    Split content into overlapping chunks.
    
    Args:
        content: Text content to chunk
        chunk_size: Maximum size per chunk
        overlap: Overlap between chunks for context
        
    Returns:
        List of content chunks
    """
    if len(content) <= chunk_size:
        return [content]
    
    chunks = []
    start = 0
    
    while start < len(content):
        end = start + chunk_size
        
        # Try to break at a natural boundary (paragraph, sentence)
        if end < len(content):
            # Look for paragraph break
            last_para = content.rfind('\n\n', start, end)
            if last_para > start + chunk_size // 2:
                end = last_para
            else:
                # Look for sentence break
                last_period = content.rfind('. ', start, end)
                if last_period > start + chunk_size // 2:
                    end = last_period + 1
        
        chunk = content[start:end].strip()
        chunks.append(chunk)
        
        # Move start forward, with overlap for context
        start = end - overlap if end < len(content) else len(content)
    
    return chunks


def compress_and_chunk_content(html: str, chunk_size: int = 50000) -> dict:
    """
    Compress HTML and split into chunks if needed.
    
    Args:
        html: Raw HTML content
        chunk_size: Maximum characters per chunk
        
    Returns:
        Dict with:
        - chunks: List of content chunks
        - total_chunks: Number of chunks
        - compressed_size: Size after compression
        - original_size: Original HTML size
    """
    original_size = len(html)
    
    # First compress
    compressed = compress_content(html, max_chars=chunk_size * 10)  # Allow larger for chunking
    compressed_size = len(compressed)
    
    # Then chunk if needed
    chunks = chunk_content(compressed, chunk_size=chunk_size)
    
    return {
        "chunks": chunks,
        "total_chunks": len(chunks),
        "compressed_size": compressed_size,
        "original_size": original_size,
        "compression_ratio": f"{(1 - compressed_size/original_size) * 100:.1f}%"
    }
