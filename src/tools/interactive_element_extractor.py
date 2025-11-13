"""
Interactive Element Extractor - Smart Element Discovery

Extracts interactive elements based on task types with semantic understanding.
Uses predefined task categories to find relevant elements efficiently.
"""

from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolResult
from src.tools.semantic_element_selector import get_element_selector
from urllib.parse import urlparse
import asyncio
import json


class InteractiveElementExtractor(BaseTool):
    """
    Extracts interactive elements based on predefined task types.

    Instead of extracting all elements, focuses on task-relevant elements
    for better performance and accuracy.
    """

    # Predefined task types with their element mappings
    TASK_TYPES = {
        "search": {
            "description": "Find and interact with search functionality",
            "selectors": [
                "input[type='text']",
                "input[type='search']",
                "input[placeholder*='search' i]",
                "input[aria-label*='search' i]",
                "input[name*='search' i]",
                "input[id*='search' i]",
                "textarea[aria-label*='search' i]",
                "button[type='submit']",
                "input[type='submit']",
                "button[aria-label*='search' i]",
                "[role='search'] input",
                "[role='search'] button"
            ],
            "categories": ["inputs", "buttons"],
            "max_elements": 10
        },

        "navigate": {
            "description": "Navigate through menus, tabs, links",
            "selectors": [
                "a[href]",
                "button:not([type='submit'])",
                "div[role='button']",
                "span[role='button']",
                "[role='tab']",
                "[role='menuitem']",
                "[onclick]",
                "nav a",
                ".menu a",
                ".navigation a"
            ],
            "categories": ["links", "buttons", "tabs"],
            "max_elements": 20
        },

        "form_fill": {
            "description": "Fill out forms with various input types",
            "selectors": [
                "input[type='text']",
                "input[type='email']",
                "input[type='password']",
                "input[type='tel']",
                "input[type='url']",
                "textarea",
                "select",
                "input[type='checkbox']",
                "input[type='radio']",
                "button[type='submit']",
                "input[type='submit']"
            ],
            "categories": ["inputs", "buttons"],
            "max_elements": 15
        },

        "extract": {
            "description": "Extract data from tables, lists, content",
            "selectors": [
                "table",
                "ul",
                "ol",
                "div[data-*]",
                "[class*='item']",
                "[class*='list']",
                "[class*='card']",
                "[role='list']",
                "[role='listitem']"
            ],
            "categories": ["containers", "lists"],
            "max_elements": 25
        },

        "click_action": {
            "description": "Perform click actions (submit, cancel, etc.)",
            "selectors": [
                "button",
                "input[type='button']",
                "input[type='submit']",
                "input[type='reset']",
                "[role='button']",
                "[onclick]",
                ".btn",
                "[class*='button']"
            ],
            "categories": ["buttons", "actions"],
            "max_elements": 15
        }
    }

    def __init__(self, logger: Optional[Any] = None):
        """
        Initialize Interactive Element Extractor.

        Args:
            logger: Optional logging service
        """
        super().__init__(logger=logger)

    @property
    def name(self) -> str:
        """Tool name for LangChain registration."""
        return "interactive_element_extractor"

    @property
    def description(self) -> str:
        """Tool description for LLM to understand when to use it."""
        return "Extract interactive elements from web pages based on task type (search, navigate, form_fill, extract, click_action). Returns categorized elements with selectors and attributes."

    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute element extraction.

        Args:
            url: URL to extract from
            task_type: Task type (search, navigate, form_fill, extract, click_action)

        Returns:
            ToolResult with categorized elements
        """
        url = kwargs.get('url')
        task_type = kwargs.get('task_type')

        if not url:
            return ToolResult(
                success=False,
                error="URL parameter is required",
                metadata={"tool": self.name}
            )

        if not task_type:
            return ToolResult(
                success=False,
                error="task_type parameter is required",
                metadata={"tool": self.name}
            )

        if task_type not in self.TASK_TYPES:
            return ToolResult(
                success=False,
                error=f"Invalid task_type: {task_type}. Valid types: {list(self.TASK_TYPES.keys())}",
                metadata={"tool": self.name}
            )

        if self.logger:
            self.logger.status(f"Extracting {task_type} elements from: {url}")

        # Extract elements
        result = self.extract_elements(url, task_type)

        if result.get('success'):
            elements = result.get('elements', {})
            metadata = {
                "tool": self.name,
                "url": url,
                "task_type": task_type,
                "total_elements": sum(len(cat) for cat in elements.values()),
                "categories": list(elements.keys())
            }

            if self.logger:
                self.logger.status(f"Extracted {metadata['total_elements']} {task_type} elements")

            return ToolResult(
                success=True,
                data=elements,
                metadata=metadata
            )
        else:
            error_msg = result.get('error', 'Unknown extraction error')
            if self.logger:
                self.logger.error(f"Element extraction failed: {error_msg}")

            return ToolResult(
                success=False,
                error=error_msg,
                metadata={
                    "tool": self.name,
                    "url": url,
                    "task_type": task_type
                }
            )

    def extract_elements(self, url: str, task_type: str) -> Dict[str, Any]:
        """
        Extract elements for the specified task type.

        Args:
            url: URL to extract from
            task_type: Task type to extract

        Returns:
            Dict with success status and extracted elements
        """
        try:
            # Run async extraction
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._extract_elements_async(url, task_type))

    async def _extract_elements_async(self, url: str, task_type: str) -> Dict[str, Any]:
        """
        Async element extraction.

        Args:
            url: URL to extract from
            task_type: Task type to extract

        Returns:
            Dict with extraction results
        """
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                try:
                    # Navigate to URL
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)

                    # Get task configuration
                    task_config = self.TASK_TYPES[task_type]
                    selectors = task_config["selectors"]
                    categories = task_config["categories"]
                    max_elements = task_config["max_elements"]

                    # Extract elements
                    elements = await self._extract_elements_by_selectors(
                        page, selectors, categories, max_elements
                    )

                    # Store elements in vector database for future semantic search
                    try:
                        selector = get_element_selector()
                        stored_count = selector.store_elements(url, elements)
                        print(f"[InteractiveElementExtractor] Stored {stored_count} elements in vector database")
                    except Exception as e:
                        print(f"[InteractiveElementExtractor] Failed to store elements: {e}")

                    return {
                        "success": True,
                        "elements": elements,
                        "task_type": task_type,
                        "url": url
                    }

                finally:
                    await browser.close()

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_type": task_type,
                "url": url
            }

    async def _extract_elements_by_selectors(
        self,
        page,
        selectors: List[str],
        categories: List[str],
        max_elements: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract elements using the provided selectors.

        Args:
            page: Playwright page
            selectors: CSS selectors to use
            categories: Categories to organize results
            max_elements: Maximum elements to extract

        Returns:
            Dict organized by categories
        """
        # Initialize result categories
        results = {cat: [] for cat in categories}
        total_extracted = 0

        # Extract elements for each selector
        for selector in selectors:
            if total_extracted >= max_elements:
                break

            try:
                # Find elements matching selector
                elements = page.locator(selector)

                # Get count
                count = await elements.count()
                if count == 0:
                    continue

                # Extract element data (limit to avoid overload)
                extract_count = min(count, max_elements - total_extracted)

                for i in range(extract_count):
                    try:
                        element_data = await self._extract_single_element_data(
                            page, selector, i
                        )

                        if element_data:
                            # Categorize the element
                            category = self._categorize_element(element_data, categories)
                            if category and len(results[category]) < max_elements // len(categories):
                                results[category].append(element_data)
                                total_extracted += 1

                    except Exception as e:
                        continue  # Skip problematic elements

            except Exception as e:
                continue  # Skip problematic selectors

        return results

    async def _extract_single_element_data(self, page, selector: str, index: int) -> Optional[Dict[str, Any]]:
        """
        Extract data for a single element.

        Args:
            page: Playwright page
            selector: CSS selector
            index: Element index

        Returns:
            Element data dict or None
        """
        try:
            # Create locator for specific element
            locator = page.locator(selector).nth(index)

            # Extract attributes and properties
            tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")

            # Get all relevant attributes
            attributes = await locator.evaluate("""
                el => {
                    const attrs = {};
                    const relevant = ['id', 'name', 'type', 'placeholder', 'aria-label',
                                    'aria-describedby', 'role', 'class', 'href', 'value',
                                    'title', 'alt', 'data-testid', 'data-cy'];

                    for (const attr of relevant) {
                        const value = el.getAttribute(attr);
                        if (value) attrs[attr] = value;
                    }

                    return attrs;
                }
            """)

            # Get text content
            text_content = await locator.text_content()
            text_content = text_content.strip() if text_content else ""

            # Get visible text (inner text)
            inner_text = await locator.inner_text()
            inner_text = inner_text.strip() if inner_text else ""

            # Generate CSS selector for this element
            css_selector = await self._generate_css_selector(page, selector, index)

            # Create semantic description for vector search
            description = self._create_element_description(tag_name, attributes, text_content, inner_text)

            return {
                "tag": tag_name,
                "selector": css_selector,
                "attributes": attributes,
                "text_content": text_content,
                "inner_text": inner_text,
                "description": description,
                "index": index
            }

        except Exception as e:
            return None

    async def _generate_css_selector(self, page, base_selector: str, index: int) -> str:
        """
        Generate a unique CSS selector for the element.

        Args:
            page: Playwright page
            base_selector: Base selector used to find element
            index: Element index

        Returns:
            Unique CSS selector
        """
        try:
            return await page.locator(base_selector).nth(index).evaluate("""
                el => {
                    // Try to create a unique selector
                    let selector = el.tagName.toLowerCase();

                    if (el.id) {
                        return `${selector}#${el.id}`;
                    }

                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(' '));
                        if (classes.length > 0) {
                            selector += '.' + classes[0];
                        }
                    }

                    // Add attribute selectors for uniqueness
                    if (el.getAttribute('aria-label')) {
                        selector += `[aria-label="${el.getAttribute('aria-label')}"]`;
                    } else if (el.getAttribute('placeholder')) {
                        selector += `[placeholder="${el.getAttribute('placeholder')}"]`;
                    } else if (el.getAttribute('name')) {
                        selector += `[name="${el.getAttribute('name')}"]`;
                    } else if (el.getAttribute('data-testid')) {
                        selector += `[data-testid="${el.getAttribute('data-testid')}"]`;
                    }

                    return selector;
                }
            """)
        except:
            return base_selector  # Fallback

    def _categorize_element(self, element_data: Dict[str, Any], categories: List[str]) -> Optional[str]:
        """
        Categorize an element into the appropriate category.

        Args:
            element_data: Element data
            categories: Available categories

        Returns:
            Category name or None
        """
        tag = element_data.get("tag", "")
        attributes = element_data.get("attributes", {})

        # Categorization logic
        if "inputs" in categories:
            if tag in ["input", "textarea", "select"]:
                return "inputs"

        if "buttons" in categories:
            if tag == "button" or (tag == "input" and attributes.get("type") in ["submit", "button"]):
                return "buttons"
            if attributes.get("role") == "button":
                return "buttons"

        if "links" in categories:
            if tag == "a" or attributes.get("href"):
                return "links"

        if "tabs" in categories:
            if attributes.get("role") == "tab":
                return "tabs"

        if "containers" in categories:
            if tag in ["table", "ul", "ol", "div"] and attributes.get("data-"):
                return "containers"

        if "lists" in categories:
            if tag in ["ul", "ol"] or attributes.get("role") == "list":
                return "lists"

        if "actions" in categories:
            if tag == "button" or attributes.get("onclick"):
                return "actions"

        # Default to first category if no match
        return categories[0] if categories else None

    def _create_element_description(self, tag: str, attributes: Dict[str, Any],
                                  text_content: str, inner_text: str) -> str:
        """
        Create a semantic description for vector search.

        Args:
            tag: Element tag
            attributes: Element attributes
            text_content: Text content
            inner_text: Inner text

        Returns:
            Semantic description string
        """
        parts = []

        # Add tag type
        if tag == "input":
            input_type = attributes.get("type", "text")
            parts.append(f"{input_type} input field")
        elif tag == "button":
            parts.append("button")
        elif tag == "a":
            parts.append("link")
        elif tag == "textarea":
            parts.append("text area")
        else:
            parts.append(f"{tag} element")

        # Add accessibility labels
        if attributes.get("aria-label"):
            parts.append(attributes["aria-label"])
        if attributes.get("placeholder"):
            parts.append(f"placeholder: {attributes['placeholder']}")
        if attributes.get("title"):
            parts.append(f"title: {attributes['title']}")

        # Add visible text
        text = inner_text or text_content
        if text and len(text) < 50:
            parts.append(f"text: {text}")

        # Add role information
        if attributes.get("role"):
            parts.append(f"role: {attributes['role']}")

        return " - ".join(parts)

    def get_available_task_types(self) -> Dict[str, str]:
        """
        Get available task types with descriptions.

        Returns:
            Dict mapping task types to descriptions
        """
        return {name: config["description"] for name, config in self.TASK_TYPES.items()}

    def get_task_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific task type.

        Args:
            task_type: Task type name

        Returns:
            Task configuration or None
        """
        return self.TASK_TYPES.get(task_type)
