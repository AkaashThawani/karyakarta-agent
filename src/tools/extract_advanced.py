"""
Advanced Data Extraction Tools

Additional specialized extraction tools:
- extract_table: HTML tables to structured data
- extract_links: Extract all links with filters
- extract_images: Extract images with metadata
- extract_text_blocks: Extract paragraphs/sections
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from lxml import html
import json
import re
from urllib.parse import urljoin, urlparse


class ExtractTableInput(BaseModel):
    """Input schema for extract_table tool."""
    content: str = Field(description="HTML content containing tables")
    table_index: Optional[int] = Field(
        default=None,
        description="Specific table index to extract (0-based). If None, extracts all tables"
    )
    include_headers: Optional[bool] = Field(
        default=True,
        description="Include table headers in output"
    )


class ExtractLinksInput(BaseModel):
    """Input schema for extract_links tool."""
    content: str = Field(description="HTML content to extract links from")
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for resolving relative links"
    )
    filter_internal: Optional[bool] = Field(
        default=False,
        description="Only include internal links (same domain)"
    )
    filter_external: Optional[bool] = Field(
        default=False,
        description="Only include external links (different domain)"
    )


class ExtractImagesInput(BaseModel):
    """Input schema for extract_images tool."""
    content: str = Field(description="HTML content containing images")
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for resolving relative image URLs"
    )
    min_width: Optional[int] = Field(
        default=0,
        description="Minimum image width (if available in HTML)"
    )
    include_metadata: Optional[bool] = Field(
        default=True,
        description="Include alt text, title, and dimensions"
    )


class ExtractTextBlocksInput(BaseModel):
    """Input schema for extract_text_blocks tool."""
    content: str = Field(description="HTML content to extract text from")
    block_type: Optional[str] = Field(
        default="paragraphs",
        description="Type of blocks: 'paragraphs', 'headings', 'lists', 'all'"
    )
    min_length: Optional[int] = Field(
        default=20,
        description="Minimum text length to include"
    )


class ExtractTableTool(BaseTool):
    """Tool for extracting HTML tables to structured data."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "extract_table"
    
    @property
    def description(self) -> str:
        return """Extract HTML tables to structured JSON data.
        
        Converts HTML tables into clean, structured data format.
        
        Parameters:
        - content: HTML containing tables
        - table_index: Specific table to extract (optional)
        - include_headers: Include table headers (default: true)
        
        Returns: JSON array of table data with rows and columns
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        content = kwargs.get("content", "")
        return bool(content)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        table_index = kwargs.get("table_index")
        include_headers = kwargs.get("include_headers", True)
        
        if not content:
            return ToolResult(success=False, error="Content is required", metadata={})
        
        try:
            doc = html.fromstring(content)
            tables = doc.xpath("//table")
            
            if not tables:
                return ToolResult(
                    success=True,
                    data=json.dumps([]),
                    metadata={"tables_found": 0}
                )
            
            result = []
            
            if table_index is not None:
                if 0 <= table_index < len(tables):
                    result.append(self._parse_table(tables[table_index], include_headers))
            else:
                for table in tables:
                    result.append(self._parse_table(table, include_headers))
            
            return ToolResult(
                success=True,
                data=json.dumps(result, indent=2),
                metadata={"tables_extracted": len(result)}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def _parse_table(self, table_elem, include_headers: bool) -> Dict[str, Any]:
        """Parse a single table element."""
        headers = []
        rows = []
        
        # Extract headers
        header_rows = table_elem.xpath(".//thead//tr | .//tr[1][.//th]")
        if header_rows and include_headers:
            for th in header_rows[0].xpath(".//th"):
                headers.append(th.text_content().strip())
        
        # Extract data rows
        data_rows = table_elem.xpath(".//tbody//tr | .//tr[not(.//th)]")
        for tr in data_rows:
            row = []
            for td in tr.xpath(".//td"):
                row.append(td.text_content().strip())
            if row:
                rows.append(row)
        
        return {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers) if headers else (len(rows[0]) if rows else 0)
        }
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ExtractTableInput)
        def extract_table(content: str, table_index: Optional[int] = None, include_headers: bool = True) -> str:
            """Extract HTML tables to structured data."""
            result = tool_instance.execute(content=content, table_index=table_index, include_headers=include_headers)
            return tool_instance.format_result(result)
        
        return extract_table


class ExtractLinksTool(BaseTool):
    """Tool for extracting links from HTML."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "extract_links"
    
    @property
    def description(self) -> str:
        return """Extract all links from HTML content with filtering options.
        
        Parameters:
        - content: HTML to extract links from
        - base_url: Base URL for resolving relative links
        - filter_internal: Only internal links (same domain)
        - filter_external: Only external links (different domain)
        
        Returns: JSON array of links with URLs and anchor text
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("content"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        base_url = kwargs.get("base_url")
        filter_internal = kwargs.get("filter_internal", False)
        filter_external = kwargs.get("filter_external", False)
        
        if not content:
            return ToolResult(success=False, error="Content is required", metadata={})
        
        try:
            doc = html.fromstring(content)
            links = []
            
            base_domain = urlparse(base_url).netloc if base_url else None
            
            for a in doc.xpath("//a[@href]"):
                href = a.get("href", "")
                text = a.text_content().strip()
                
                # Resolve relative URLs
                if base_url and href:
                    href = urljoin(base_url, href)
                
                # Apply filters
                if filter_internal or filter_external:
                    link_domain = urlparse(href).netloc
                    
                    if filter_internal and link_domain != base_domain:
                        continue
                    if filter_external and link_domain == base_domain:
                        continue
                
                if href:
                    links.append({
                        "url": href,
                        "text": text,
                        "title": a.get("title", "")
                    })
            
            return ToolResult(
                success=True,
                data=json.dumps(links, indent=2),
                metadata={"links_found": len(links)}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ExtractLinksInput)
        def extract_links(content: str, base_url: Optional[str] = None, filter_internal: bool = False, filter_external: bool = False) -> str:
            """Extract links from HTML with filtering."""
            result = tool_instance.execute(content=content, base_url=base_url, filter_internal=filter_internal, filter_external=filter_external)
            return tool_instance.format_result(result)
        
        return extract_links


class ExtractImagesTool(BaseTool):
    """Tool for extracting images from HTML."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "extract_images"
    
    @property
    def description(self) -> str:
        return """Extract images from HTML with metadata.
        
        Parameters:
        - content: HTML containing images
        - base_url: Base URL for resolving relative paths
        - min_width: Minimum image width filter
        - include_metadata: Include alt text and dimensions
        
        Returns: JSON array of images with URLs and metadata
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("content"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        base_url = kwargs.get("base_url")
        min_width = kwargs.get("min_width", 0)
        include_metadata = kwargs.get("include_metadata", True)
        
        if not content:
            return ToolResult(success=False, error="Content is required", metadata={})
        
        try:
            doc = html.fromstring(content)
            images = []
            
            for img in doc.xpath("//img[@src]"):
                src = img.get("src", "")
                
                # Resolve relative URLs
                if base_url and src:
                    src = urljoin(base_url, src)
                
                # Check width filter
                width = img.get("width")
                if width and width.isdigit() and int(width) < min_width:
                    continue
                
                image_data = {"url": src}
                
                if include_metadata:
                    image_data.update({
                        "alt": img.get("alt", ""),
                        "title": img.get("title", ""),
                        "width": img.get("width", ""),
                        "height": img.get("height", "")
                    })
                
                images.append(image_data)
            
            return ToolResult(
                success=True,
                data=json.dumps(images, indent=2),
                metadata={"images_found": len(images)}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ExtractImagesInput)
        def extract_images(content: str, base_url: Optional[str] = None, min_width: int = 0, include_metadata: bool = True) -> str:
            """Extract images from HTML with metadata."""
            result = tool_instance.execute(content=content, base_url=base_url, min_width=min_width, include_metadata=include_metadata)
            return tool_instance.format_result(result)
        
        return extract_images


class ExtractTextBlocksTool(BaseTool):
    """Tool for extracting text blocks from HTML."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "extract_text_blocks"
    
    @property
    def description(self) -> str:
        return """Extract text blocks from HTML (paragraphs, headings, lists).
        
        Parameters:
        - content: HTML to extract text from
        - block_type: 'paragraphs', 'headings', 'lists', 'all'
        - min_length: Minimum text length
        
        Returns: JSON array of text blocks with type and content
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("content"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        block_type = kwargs.get("block_type", "paragraphs")
        min_length = kwargs.get("min_length", 20)
        
        if not content:
            return ToolResult(success=False, error="Content is required", metadata={})
        
        try:
            doc = html.fromstring(content)
            blocks = []
            
            if block_type in ["paragraphs", "all"]:
                for p in doc.xpath("//p"):
                    text = p.text_content().strip()
                    if len(text) >= min_length:
                        blocks.append({"type": "paragraph", "content": text})
            
            if block_type in ["headings", "all"]:
                for h in doc.xpath("//h1 | //h2 | //h3 | //h4 | //h5 | //h6"):
                    text = h.text_content().strip()
                    if len(text) >= min_length:
                        blocks.append({"type": "heading", "content": text, "level": h.tag})
            
            if block_type in ["lists", "all"]:
                for li in doc.xpath("//li"):
                    text = li.text_content().strip()
                    if len(text) >= min_length:
                        blocks.append({"type": "list_item", "content": text})
            
            return ToolResult(
                success=True,
                data=json.dumps(blocks, indent=2),
                metadata={"blocks_found": len(blocks)}
            )
            
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ExtractTextBlocksInput)
        def extract_text_blocks(content: str, block_type: str = "paragraphs", min_length: int = 20) -> str:
            """Extract text blocks from HTML."""
            result = tool_instance.execute(content=content, block_type=block_type, min_length=min_length)
            return tool_instance.format_result(result)
        
        return extract_text_blocks
