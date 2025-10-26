"""
Extractor Tool - Extract data from various formats

Uses open-source libraries:
- lxml for HTML/XML parsing
- pandas for CSV/table handling
- json (built-in) for JSON processing

For library details, see: docs/LIBRARY_USAGE_GUIDE.md
"""

from typing import Optional
from pydantic import BaseModel, Field
from lxml import html
from lxml import etree  # type: ignore
import pandas as pd
import json
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


class ExtractorInput(BaseModel):
    """Input schema for data extractor tool."""
    data_type: str = Field(
        description=(
            "The type of data to extract. Must be one of: "
            "'json' (JSON data), 'html' (HTML content), 'xml' (XML data), "
            "'csv' (CSV data), or 'table' (HTML tables). "
            "Example: 'json'"
        )
    )
    content: str = Field(
        description=(
            "The actual content to extract data from. "
            "For JSON: provide JSON string. "
            "For HTML/XML: provide HTML/XML string. "
            "For CSV: provide CSV text. "
            "Example: '{\"user\": {\"name\": \"John\"}}'"
        )
    )
    path: Optional[str] = Field(
        default="",
        description=(
            "Optional path or selector for extraction. "
            "For JSON: use dot notation (e.g., 'user.profile.name'). "
            "For HTML/XML: use XPath (e.g., '//div[@class=\"content\"]'). "
            "For tables: use index number (e.g., '0' for first table). "
            "Leave empty to extract all content."
        )
    )


class ExtractorTool(BaseTool):
    """
    Tool for extracting data from various formats.
    
    Supports:
    - JSON path extraction
    - HTML element extraction (XPath, CSS selectors)
    - XML data extraction
    - CSV parsing
    - HTML table extraction
    """
    
    def __init__(self, logger: Optional[LoggingService] = None):
        """
        Initialize the extractor tool.
        
        Args:
            logger: Optional logging service
        """
        super().__init__(logger)
    
    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "extract_data"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """Extract and parse data from various formats.
        
        Use this when you need to:
        - Extract specific fields from JSON
        - Parse HTML content with XPath
        - Extract data from XML
        - Parse CSV data
        - Extract tables from HTML
        
        Supported data types:
        - json: Extract data using dot notation (e.g., 'user.profile.name')
        - html: Extract using XPath selectors (e.g., '//div[@class="content"]')
        - xml: Extract using XPath
        - csv: Parse CSV data into formatted table
        - table: Extract HTML tables (provide index or extract all)
        
        Parameters:
        - data_type: Type of data ('json', 'html', 'xml', 'csv', 'table')
        - content: The actual data content to parse
        - path: Optional selector/path for extraction
        
        Examples:
        - extract_data(data_type="json", content='{"user":{"name":"John"}}', path="user.name")  # Returns "John"
        - extract_data(data_type="html", content="<div>Hello</div>", path="//div/text()")  # Returns "Hello"
        - extract_data(data_type="csv", content="name,age\\nJohn,30\\nJane,25")  # Returns formatted table
        """
    
    def validate_params(self, **kwargs) -> bool:
        """
        Validate extractor parameters.
        
        Args:
            **kwargs: Should contain 'data_type' and 'content'
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        # Check required parameters
        if "data_type" not in kwargs or "content" not in kwargs:
            return False
        
        data_type = kwargs.get("data_type", "").lower()
        valid_types = ["json", "html", "xml", "csv", "table"]
        
        if data_type not in valid_types:
            return False
        
        content = kwargs.get("content")
        if not isinstance(content, str) or not content.strip():
            return False
        
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute the extractor.
        
        Args:
            **kwargs: Must contain:
                - data_type: Type of data (json|html|xml|csv|table)
                - content: The content to extract from
                - path: Optional path/selector for extraction
            
        Returns:
            ToolResult with extracted data or error
        """
        # Handle nested kwargs
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        data_type = kwargs.get("data_type", "").lower()
        content = kwargs.get("content", "")
        path = kwargs.get("path", "")
        
        if self.logger:
            self.logger.status(f"Extracting {data_type} data...")
        
        try:
            if data_type == "json":
                result = self._extract_json(content, path)
            elif data_type == "html":
                result = self._extract_html(content, path)
            elif data_type == "xml":
                result = self._extract_xml(content, path)
            elif data_type == "csv":
                result = self._extract_csv(content)
            elif data_type == "table":
                result = self._extract_table(content, path)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unsupported data type: {data_type}",
                    metadata={"data_type": data_type}
                )
            
            if self.logger:
                self.logger.status(f"Extracted {len(str(result))} characters of data")
            
            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "data_type": data_type,
                    "path": path,
                    "result_size": len(str(result))
                }
            )
            
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"data_type": data_type, "path": path}
            )
    
    def _extract_json(self, content: str, path: str) -> str:
        """Extract data from JSON using path notation."""
        data = json.loads(content)
        
        if not path:
            return json.dumps(data, indent=2)
        
        # Navigate path (e.g., "user.profile.name")
        keys = path.split('.')
        result = data
        
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            elif isinstance(result, list) and key.isdigit():
                result = result[int(key)]
            else:
                return f"Path not found: {path}"
            
            if result is None:
                return f"Path not found: {path}"
        
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result)
    
    def _extract_html(self, content: str, xpath: str) -> str:
        """Extract data from HTML using XPath."""
        doc = html.fromstring(content)
        
        if not xpath:
            # Return text content if no xpath
            return doc.text_content().strip()
        
        # Extract using XPath
        results = doc.xpath(xpath)
        
        if not results:
            return "No elements found"
        
        # Format results
        extracted = []
        for item in results:
            if isinstance(item, str):
                extracted.append(item)
            elif hasattr(item, 'text_content'):
                extracted.append(item.text_content().strip())
            else:
                extracted.append(str(item))
        
        return "\n".join(extracted)
    
    def _extract_xml(self, content: str, xpath: str) -> str:
        """Extract data from XML using XPath."""
        root = etree.fromstring(content.encode('utf-8'))
        
        if not xpath:
            # Return all text if no xpath
            return etree.tostring(root, pretty_print=True, encoding='unicode')
        
        # Extract using XPath
        results = root.xpath(xpath)
        
        if not results:
            return "No elements found"
        
        # Format results
        extracted = []
        for item in results:
            if isinstance(item, str):
                extracted.append(item)
            elif hasattr(item, 'text'):
                extracted.append(item.text or "")
            else:
                extracted.append(etree.tostring(item, encoding='unicode'))
        
        return "\n".join(extracted)
    
    def _extract_csv(self, content: str) -> str:
        """Extract and format CSV data."""
        from io import StringIO
        
        # Parse CSV using pandas
        df = pd.read_csv(StringIO(content))
        
        # Return formatted table
        return df.to_string(index=False)
    
    def _extract_table(self, content: str, selector: str) -> str:
        """Extract HTML tables and format them."""
        # Parse HTML and extract tables using pandas
        tables = pd.read_html(content)
        
        if not tables:
            return "No tables found"
        
        # If selector is a number, use as index
        if selector and selector.isdigit():
            table_index = int(selector)
            if table_index < len(tables):
                return tables[table_index].to_string(index=False)
        
        # Otherwise return all tables
        result = []
        for i, table in enumerate(tables):
            result.append(f"Table {i + 1}:")
            result.append(table.to_string(index=False))
            result.append("")
        
        return "\n".join(result)
    
    def as_langchain_tool(self):
        """
        Convert to LangChain tool with proper schema.
        
        Returns:
            LangChain tool with input schema
        """
        tool_instance = self
        
        @tool(args_schema=ExtractorInput)
        def extract_data(data_type: str, content: str, path: str = "") -> str:
            """Extract and parse data from various formats (JSON, HTML, XML, CSV, tables)."""
            result = tool_instance.execute(data_type=data_type, content=content, path=path)
            return tool_instance.format_result(result)
        
        return extract_data
