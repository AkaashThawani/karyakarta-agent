"""
Content Extractor Tool - LangChain-compatible wrapper

Wraps ContentExtractor in a BaseTool for use in agent workflows.
Provides clean content extraction for research tasks.
"""

from typing import Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult
from src.tools.content_extractor import ContentExtractor


class ContentExtractorTool(BaseTool):
    """
    Tool for extracting clean, readable content from web pages.

    Uses ContentExtractor to strip HTML clutter and return clean text
    perfect for LLM analysis and research tasks.

    Features:
    - Fast content extraction (1-2 seconds)
    - Removes scripts, styles, CSS classes
    - Keeps semantic content tags
    - Clean output for research
    """

    def __init__(self, logger: Optional[Any] = None):
        """
        Initialize Content Extractor Tool.

        Args:
            logger: Optional logging service
        """
        super().__init__(logger=logger)
        self.extractor = ContentExtractor()

    @property
    def name(self) -> str:
        """Tool name for LangChain registration."""
        return "content_extractor"

    @property
    def description(self) -> str:
        """Tool description for LLM to understand when to use it."""
        return "Extract clean, readable content from web pages for research and analysis. Removes scripts, styles, and HTML clutter while preserving semantic content."

    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute content extraction implementation.

        Args:
            **kwargs: Tool parameters (url required)

        Returns:
            ToolResult with clean content
        """
        url = kwargs.get('url')
        if not url:
            return ToolResult(
                success=False,
                error="URL parameter is required",
                metadata={"tool": self.name}
            )

        if self.logger:
            self.logger.status(f"Extracting clean content from: {url}")

        # Extract content
        result = self.extractor.extract_content(url)

        if result.get('success'):
            content = result.get('content', '')
            metadata = {
                "tool": self.name,
                "url": url,
                "title": result.get('title'),
                "domain": result.get('domain'),
                "extraction_time": result.get('extraction_time', 0),
                "content_length": result.get('content_length', 0),
                "word_count": result.get('word_count', 0)
            }

            if self.logger:
                self.logger.status(f"Successfully extracted {len(content)} characters from {url}")

            return ToolResult(
                success=True,
                data={
                    "content": content,
                    "title": result.get('title'),
                    "url": url,
                    "metadata": metadata
                },
                metadata=metadata
            )
        else:
            error_msg = result.get('error', 'Unknown extraction error')
            if self.logger:
                self.logger.error(f"Content extraction failed: {error_msg}")

            return ToolResult(
                success=False,
                error=error_msg,
                metadata={
                    "tool": self.name,
                    "url": url,
                    "extraction_time": result.get('extraction_time', 0)
                }
            )

    def execute(self, **kwargs) -> ToolResult:
        """
        Execute content extraction.

        Args:
            url (str): URL to extract content from

        Returns:
            ToolResult with clean content
        """
        try:
            url = kwargs.get('url')
            if not url:
                return ToolResult(
                    success=False,
                    error="URL parameter is required",
                    metadata={"tool": self.name}
                )

            if self.logger:
                self.logger.status(f"Extracting clean content from: {url}")

            # Extract content
            result = self.extractor.extract_content(url)

            if result.get('success'):
                content = result.get('content', '')
                metadata = {
                    "tool": self.name,
                    "url": url,
                    "title": result.get('title'),
                    "domain": result.get('domain'),
                    "extraction_time": result.get('extraction_time', 0),
                    "content_length": result.get('content_length', 0),
                    "word_count": result.get('word_count', 0)
                }

                if self.logger:
                    self.logger.status(f"Successfully extracted {len(content)} characters from {url}")

                return ToolResult(
                    success=True,
                    data={
                        "content": content,
                        "title": result.get('title'),
                        "url": url,
                        "metadata": metadata
                    },
                    metadata=metadata
                )
            else:
                error_msg = result.get('error', 'Unknown extraction error')
                if self.logger:
                    self.logger.error(f"Content extraction failed: {error_msg}")

                return ToolResult(
                    success=False,
                    error=error_msg,
                    metadata={
                        "tool": self.name,
                        "url": url,
                        "extraction_time": result.get('extraction_time', 0)
                    }
                )

        except Exception as e:
            error_msg = f"Content extraction error: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)

            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"tool": self.name}
            )

    def as_langchain_tool(self):
        """Convert to LangChain tool format."""
        from langchain_core.tools import Tool

        def extract_content(url: str) -> str:
            """Extract clean content from a URL."""
            result = self.execute(url=url)
            if result.success:
                data = result.data
                if isinstance(data, dict):
                    content = data.get('content', '')
                    title = data.get('title', '')
                    if title and content:
                        return f"Title: {title}\n\nContent:\n{content}"
                    return content
                return str(data)
            else:
                return f"Error extracting content: {result.error}"

        return Tool(
            name=self.name,
            description=self.description,
            func=extract_content
        )

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get tool capabilities and metadata.

        Returns:
            Dict with tool information
        """
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": ["content_extraction", "web_scraping", "text_cleaning"],
            "input_parameters": {
                "url": {
                    "type": "string",
                    "required": True,
                    "description": "URL to extract content from"
                }
            },
            "output_format": {
                "content": "Clean, readable text content",
                "title": "Page title",
                "metadata": "Extraction metadata (timing, word count, etc.)"
            },
            "performance": "1-2 seconds per extraction",
            "use_cases": ["research", "content analysis", "web reading"]
        }
