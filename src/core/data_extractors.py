"""
Data Extractors - Pure functions for extracting structured data from tool outputs

These are pure, stateless functions with ZERO dependencies on tool implementations.
Each extractor takes raw data and returns structured output according to the schema.

Usage:
    from src.core.data_extractors import get_extractor
    
    extractor = get_extractor("extract_urls_from_text")
    urls = extractor("Visit https://example.com for more info")
    # Returns: ["https://example.com"]
"""

import re
from typing import Any, List, Dict, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup


def identity(data: Any) -> Any:
    """
    Return data as-is without modification.
    
    Args:
        data: Any data type
        
    Returns:
        Same data unchanged
    """
    return data


def extract_urls_from_text(text: str) -> List[str]:
    """
    Extract all URLs from text using regex.
    
    Args:
        text: Text containing URLs
        
    Returns:
        List of extracted URLs (cleaned)
    """
    if not isinstance(text, str):
        return []
    
    # Match http(s) URLs
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(pattern, text)
    
    # Clean URLs (remove trailing punctuation)
    cleaned_urls = []
    for url in urls:
        cleaned = url.rstrip(',.;:!?)')
        # Remove common trailing characters
        while cleaned and cleaned[-1] in ',.;:!?)':
            cleaned = cleaned[:-1]
        if cleaned:
            cleaned_urls.append(cleaned)
    
    return cleaned_urls


def extract_snippets_from_text(text: str) -> List[str]:
    """
    Extract search snippets from text.
    
    Snippets are text blocks longer than 50 characters,
    typically descriptions from search results.
    
    Args:
        text: Search results text
        
    Returns:
        List of text snippets (max 10)
    """
    if not isinstance(text, str):
        return []
    
    # Split by common snippet separators
    lines = text.split('\n')
    
    # Filter for meaningful lines (not just URLs or short text)
    snippets = []
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip lines that are just URLs
        if line.startswith('http'):
            continue
        
        # Keep lines longer than 50 characters
        if len(line) > 50:
            snippets.append(line)
    
    # Return top 10 snippets
    return snippets[:10]


def count_records(records: Any) -> int:
    """
    Count number of records in a list.
    
    Args:
        records: List of records or any data
        
    Returns:
        Count of items (0 if not a list)
    """
    if isinstance(records, list):
        return len(records)
    elif isinstance(records, dict):
        return len(records)
    return 0


def extract_field_names(records: Any) -> List[str]:
    """
    Extract field names from list of records.
    
    Args:
        records: List of dict records
        
    Returns:
        List of field names from first record
    """
    if not isinstance(records, list) or not records:
        return []
    
    first_record = records[0]
    if isinstance(first_record, dict):
        return list(first_record.keys())
    
    return []


def get_current_url(data: Any) -> Optional[str]:
    """
    Extract current URL from page data or response.
    
    Args:
        data: Page data (dict, string, or other)
        
    Returns:
        Current URL or None
    """
    if isinstance(data, dict):
        # Try common field names
        for field in ['url', 'current_url', 'page_url', 'location']:
            if field in data:
                return data[field]
    
    if isinstance(data, str):
        # Try to extract URL from string
        urls = extract_urls_from_text(data)
        if urls:
            return urls[0]
    
    return None


def extract_json_field(data: Any, field: str) -> Any:
    """
    Extract specific field from JSON object.
    
    Args:
        data: Dict/JSON object
        field: Field name to extract
        
    Returns:
        Field value or None
    """
    if isinstance(data, dict):
        return data.get(field)
    return None


def extract_text_from_html(html: str) -> str:
    """
    Extract plain text from HTML content.
    
    Args:
        html: HTML string
        
    Returns:
        Plain text with tags removed
    """
    if not isinstance(html, str):
        return ""
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        print(f"[Extractor] HTML text extraction failed: {e}")
        return ""


def extract_links_from_html(html: str) -> List[str]:
    """
    Extract all links from HTML content.
    
    Args:
        html: HTML string
        
    Returns:
        List of absolute URLs
    """
    if not isinstance(html, str):
        return []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip anchors and javascript links
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Keep absolute URLs
            if href.startswith(('http://', 'https://')):
                links.append(href)
        
        return links
    except Exception as e:
        print(f"[Extractor] HTML link extraction failed: {e}")
        return []


def extract_status_code(data: Any) -> Optional[int]:
    """
    Extract HTTP status code from response data.
    
    Args:
        data: Response data (dict or other)
        
    Returns:
        Status code or None
    """
    if isinstance(data, dict):
        # Try common field names
        for field in ['status_code', 'statusCode', 'status', 'code']:
            if field in data:
                value = data[field]
                if isinstance(value, int):
                    return value
                try:
                    return int(value)
                except (ValueError, TypeError):
                    pass
    
    return None


def extract_response_headers(data: Any) -> Dict[str, Any]:
    """
    Extract HTTP response headers.
    
    Args:
        data: Response data
        
    Returns:
        Headers dict or empty dict
    """
    if isinstance(data, dict):
        for field in ['headers', 'responseHeaders', 'response_headers']:
            if field in data and isinstance(data[field], dict):
                return data[field]
    
    return {}


def extract_file_path(data: Any) -> Optional[str]:
    """
    Extract file path from result data.
    
    Args:
        data: Result data (dict or string)
        
    Returns:
        File path or None
    """
    if isinstance(data, str):
        # Check if it looks like a file path
        if '/' in data or '\\' in data:
            return data
    
    if isinstance(data, dict):
        for field in ['file_path', 'path', 'filepath', 'file']:
            if field in data:
                return str(data[field])
    
    return None


# Registry of all available extractors
EXTRACTORS = {
    "identity": identity,
    "extract_urls_from_text": extract_urls_from_text,
    "extract_snippets_from_text": extract_snippets_from_text,
    "count_records": count_records,
    "extract_field_names": extract_field_names,
    "get_current_url": get_current_url,
    "extract_json_field": extract_json_field,
    "extract_text_from_html": extract_text_from_html,
    "extract_links_from_html": extract_links_from_html,
    "extract_status_code": extract_status_code,
    "extract_response_headers": extract_response_headers,
    "extract_file_path": extract_file_path,
}


def get_extractor(name: str):
    """
    Get extractor function by name.
    
    Args:
        name: Extractor name from schema
        
    Returns:
        Extractor function (defaults to identity if not found)
    """
    extractor = EXTRACTORS.get(name)
    if extractor is None:
        print(f"[Extractor] Warning: Unknown extractor '{name}', using identity")
        return identity
    return extractor


def list_extractors() -> List[str]:
    """
    List all available extractor names.
    
    Returns:
        List of extractor names
    """
    return list(EXTRACTORS.keys())
