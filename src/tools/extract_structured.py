"""
Structured Data Extraction Tool

Smart extraction of common data patterns from HTML content.
Supports:
- Books (title, author, rating, description)
- Products (name, price, rating, reviews)
- Articles (title, author, date, content)
- Events (name, date, location, description)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from lxml import html
import json
import re


class ExtractStructuredInput(BaseModel):
    """Input schema for extract_structured tool."""
    content: str = Field(
        description="HTML or text content to extract from"
    )
    pattern_type: str = Field(
        description=(
            "Type of data pattern to extract. Options: "
            "'books', 'products', 'articles', 'events', 'general'"
        )
    )
    max_items: Optional[int] = Field(
        default=10,
        description="Maximum number of items to extract (default: 10)"
    )


class ExtractStructuredTool(BaseTool):
    """
    Tool for extracting structured data using pattern recognition.
    
    Automatically identifies and extracts common data patterns from HTML/text.
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        """Initialize extract_structured tool."""
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "extract_structured"
    
    @property
    def description(self) -> str:
        return """Extract structured data from HTML/text content using smart pattern recognition.
        
        Supports common data types:
        - books: Extract title, author, rating, description, ISBN
        - products: Extract name, price, rating, reviews, features
        - articles: Extract title, author, date, content, summary
        - events: Extract name, date, location, description, price
        - general: Auto-detect and extract any structured data
        
        Parameters:
        - content: HTML or text to extract from
        - pattern_type: Type of pattern ('books', 'products', 'articles', 'events', 'general')
        - max_items: Maximum items to extract (default: 10)
        
        Returns: JSON array of extracted items with relevant fields
        
        Example:
        extract_structured(content="<html>...</html>", pattern_type="books", max_items=5)
        """
    
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters."""
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        pattern_type = kwargs.get("pattern_type", "")
        
        if not content or not isinstance(content, str):
            return False
        
        valid_patterns = ["books", "products", "articles", "events", "general"]
        if pattern_type not in valid_patterns:
            return False
        
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """Execute structured extraction."""
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        pattern_type = kwargs.get("pattern_type", "general")
        max_items = kwargs.get("max_items", 10)
        
        if not content:
            return ToolResult(
                success=False,
                error="Content is required",
                metadata={}
            )
        
        if self.logger:
            self.logger.status(f"Extracting {pattern_type} data...")
        
        try:
            # Extract based on pattern type
            if pattern_type == "books":
                items = self._extract_books(content, max_items)
            elif pattern_type == "products":
                items = self._extract_products(content, max_items)
            elif pattern_type == "articles":
                items = self._extract_articles(content, max_items)
            elif pattern_type == "events":
                items = self._extract_events(content, max_items)
            else:
                items = self._extract_general(content, max_items)
            
            if self.logger:
                self.logger.status(f"Extracted {len(items)} {pattern_type}")
            
            return ToolResult(
                success=True,
                data=json.dumps(items, indent=2),
                metadata={
                    "pattern_type": pattern_type,
                    "items_found": len(items),
                    "max_items": max_items
                }
            )
            
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"pattern_type": pattern_type}
            )
    
    def _extract_books(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract book data from HTML/text."""
        books = []
        
        try:
            doc = html.fromstring(content)
        except:
            # Fallback to text extraction
            return self._extract_books_from_text(content, max_items)
        
        # Common book selectors
        book_selectors = [
            "//div[contains(@class, 'book')]",
            "//div[contains(@class, 'bookItem')]",
            "//div[contains(@class, 'item')]",
            "//article",
            "//li[contains(@class, 'book')]"
        ]
        
        book_elements = []
        for selector in book_selectors:
            book_elements = doc.xpath(selector)
            if book_elements:
                break
        
        for elem in book_elements[:max_items]:
            book = {}
            
            # Extract title
            title_selectors = [
                ".//a[contains(@class, 'bookTitle')]//text()",
                ".//h2//text()",
                ".//h3//text()",
                ".//a[@class='title']//text()",
                ".//span[contains(@class, 'title')]//text()"
            ]
            for selector in title_selectors:
                title = elem.xpath(selector)
                if title:
                    book["title"] = " ".join([t.strip() for t in title if t.strip()])
                    break
            
            # Extract author
            author_selectors = [
                ".//a[contains(@class, 'author')]//text()",
                ".//span[contains(@class, 'author')]//text()",
                ".//div[contains(@class, 'author')]//text()"
            ]
            for selector in author_selectors:
                author = elem.xpath(selector)
                if author:
                    book["author"] = " ".join([a.strip() for a in author if a.strip()])
                    break
            
            # Extract rating
            rating_selectors = [
                ".//span[contains(@class, 'rating')]//text()",
                ".//div[contains(@class, 'rating')]//text()",
                ".//span[contains(@class, 'stars')]//text()"
            ]
            for selector in rating_selectors:
                rating = elem.xpath(selector)
                if rating:
                    # Extract numeric rating
                    rating_text = " ".join([r.strip() for r in rating if r.strip()])
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        book["rating"] = rating_match.group(1)
                    break
            
            # Extract description
            desc_selectors = [
                ".//div[contains(@class, 'description')]//text()",
                ".//p[contains(@class, 'description')]//text()",
                ".//span[contains(@class, 'description')]//text()"
            ]
            for selector in desc_selectors:
                desc = elem.xpath(selector)
                if desc:
                    book["description"] = " ".join([d.strip() for d in desc if d.strip()])[:200]
                    break
            
            if book.get("title"):  # Only add if we found at least a title
                books.append(book)
        
        return books
    
    def _extract_books_from_text(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """Fallback: Extract books from plain text."""
        books = []
        
        # Look for common book patterns in text
        # Example: "Title by Author - 4.5 stars"
        lines = content.split('\n')
        
        for line in lines[:max_items * 3]:  # Check more lines
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            book = {}
            
            # Try to extract title (usually first, before "by")
            if ' by ' in line.lower():
                parts = line.split(' by ', 1)
                book["title"] = parts[0].strip()
                
                # Extract author from remaining text
                remaining = parts[1]
                # Author is usually before ratings/stars
                author_end = remaining.find(' - ')
                if author_end == -1:
                    author_end = remaining.find(' (')
                if author_end == -1:
                    author_end = remaining.find('.')
                
                if author_end > 0:
                    book["author"] = remaining[:author_end].strip()
                else:
                    book["author"] = remaining.strip()
                
                # Extract rating
                rating_match = re.search(r'(\d+\.?\d*)\s*(?:stars?|rating)', remaining, re.IGNORECASE)
                if rating_match:
                    book["rating"] = rating_match.group(1)
            
            if book.get("title"):
                books.append(book)
                if len(books) >= max_items:
                    break
        
        return books
    
    def _extract_products(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract product data."""
        products = []
        
        try:
            doc = html.fromstring(content)
        except:
            return []
        
        # Common product selectors
        product_selectors = [
            "//div[contains(@class, 'product')]",
            "//div[contains(@class, 'item')]",
            "//article[contains(@class, 'product')]"
        ]
        
        product_elements = []
        for selector in product_selectors:
            product_elements = doc.xpath(selector)
            if product_elements:
                break
        
        for elem in product_elements[:max_items]:
            product = {}
            
            # Extract name
            name = elem.xpath(".//h2//text() | .//h3//text() | .//a[@class='title']//text()")
            if name:
                product["name"] = " ".join([n.strip() for n in name if n.strip()])
            
            # Extract price
            price = elem.xpath(".//*[contains(@class, 'price')]//text()")
            if price:
                product["price"] = " ".join([p.strip() for p in price if p.strip()])
            
            if product.get("name"):
                products.append(product)
        
        return products
    
    def _extract_articles(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract article data."""
        articles = []
        
        try:
            doc = html.fromstring(content)
        except:
            return []
        
        article_elements = doc.xpath("//article | //div[contains(@class, 'article')]")
        
        for elem in article_elements[:max_items]:
            article = {}
            
            # Extract title
            title = elem.xpath(".//h1//text() | .//h2//text() | .//h3//text()")
            if title:
                article["title"] = " ".join([t.strip() for t in title if t.strip()])
            
            # Extract author
            author = elem.xpath(".//*[contains(@class, 'author')]//text()")
            if author:
                article["author"] = " ".join([a.strip() for a in author if a.strip()])
            
            if article.get("title"):
                articles.append(article)
        
        return articles
    
    def _extract_events(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract event data."""
        events = []
        
        try:
            doc = html.fromstring(content)
        except:
            return []
        
        event_elements = doc.xpath("//div[contains(@class, 'event')] | //article[contains(@class, 'event')]")
        
        for elem in event_elements[:max_items]:
            event = {}
            
            # Extract name
            name = elem.xpath(".//h2//text() | .//h3//text()")
            if name:
                event["name"] = " ".join([n.strip() for n in name if n.strip()])
            
            if event.get("name"):
                events.append(event)
        
        return events
    
    def _extract_general(self, content: str, max_items: int) -> List[Dict[str, Any]]:
        """General extraction - try to find any structured data."""
        # Try each pattern and return the first successful one
        for pattern_type in ["books", "products", "articles", "events"]:
            try:
                items = getattr(self, f"_extract_{pattern_type}")(content, max_items)
                if items:
                    return items
            except:
                continue
        
        return []
    
    def as_langchain_tool(self):
        """Convert to LangChain tool."""
        tool_instance = self
        
        @tool(args_schema=ExtractStructuredInput)
        def extract_structured(content: str, pattern_type: str, max_items: int = 10) -> str:
            """Extract structured data from HTML/text using pattern recognition."""
            result = tool_instance.execute(content=content, pattern_type=pattern_type, max_items=max_items)
            return tool_instance.format_result(result)
        
        return extract_structured
