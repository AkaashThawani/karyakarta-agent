"""
Interactive Element Extractor Tool - BaseTool wrapper

Provides LangChain-compatible interface for the InteractiveElementExtractor.
"""

from typing import Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult
from src.tools.interactive_element_extractor import InteractiveElementExtractor


class InteractiveElementExtractorTool(BaseTool):
    """
    Tool wrapper for InteractiveElementExtractor.

    Provides LangChain-compatible interface for element extraction
    based on predefined task types.
    """

    def __init__(self, logger: Optional[Any] = None):
        """
        Initialize Interactive Element Extractor Tool.

        Args:
            logger: Optional logging service
        """
        super().__init__(logger=logger)
        self.extractor = InteractiveElementExtractor(logger=logger)

    @property
    def name(self) -> str:
        """Tool name for LangChain registration."""
        return "interactive_element_extractor"

    @property
    def description(self) -> str:
        """Tool description for LLM to understand when to use it."""
        task_types = list(self.extractor.TASK_TYPES.keys())
        return f"Extract interactive elements from web pages based on task type. Valid task types: {', '.join(task_types)}. Returns categorized elements with selectors and attributes for semantic element matching."

    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute element extraction.

        Args:
            url: URL to extract from
            task_type: Task type (search, navigate, form_fill, extract, click_action)

        Returns:
            ToolResult with categorized elements
        """
        return self.extractor._execute_impl(**kwargs)

    def get_available_task_types(self) -> Dict[str, str]:
        """
        Get available task types with descriptions.

        Returns:
            Dict mapping task types to descriptions
        """
        return self.extractor.get_available_task_types()

    def get_task_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific task type.

        Args:
            task_type: Task type name

        Returns:
            Task configuration or None
        """
        return self.extractor.get_task_config(task_type)
