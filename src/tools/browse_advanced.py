"""
Advanced Browsing Tools - Dynamic Content Handling

Tools for handling complex web scraping scenarios:
- Dynamic content loading
- Infinite scroll
- Interactive elements
- Form submissions

Uses Browserless Cloud with Playwright for robust scraping.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
import asyncio
import os


class BrowseAndWaitInput(BaseModel):
    """Input schema for browse_and_wait tool."""
    url: str = Field(
        description="The URL to browse"
    )
    wait_selector: Optional[str] = Field(
        default=None,
        description=(
            "CSS selector to wait for before extracting content. "
            "Example: '.book-item', '#content-loaded', 'div.results'. "
            "If not provided, waits for page load event."
        )
    )
    timeout: Optional[int] = Field(
        default=10,
        description="Maximum time to wait in seconds (default: 10)"
    )


class BrowseWithScrollInput(BaseModel):
    """Input schema for browse_with_scroll tool."""
    url: str = Field(
        description="The URL to browse"
    )
    scroll_times: Optional[int] = Field(
        default=3,
        description="Number of times to scroll down (default: 3)"
    )
    wait_between: Optional[int] = Field(
        default=1000,
        description="Milliseconds to wait between scrolls (default: 1000)"
    )


class BrowseWithClickInput(BaseModel):
    """Input schema for browse_with_click tool."""
    url: str = Field(
        description="The URL to browse"
    )
    click_selector: str = Field(
        description=(
            "CSS selector of element to click. "
            "Example: 'button.load-more', '#show-all', 'a.next-page'"
        )
    )
    wait_after: Optional[int] = Field(
        default=2,
        description="Seconds to wait after clicking (default: 2)"
    )


class BrowseAndWaitTool(BaseTool):
    """
    Tool for browsing pages with dynamic content that requires waiting.
    
    Handles JavaScript-heavy pages that load content asynchronously.
    Waits for specific elements to appear before extracting content.
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        """Initialize browse_and_wait tool."""
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_and_wait"
    
    @property
    def description(self) -> str:
        return """Browse a webpage and wait for dynamic content to load.
        
        Use this tool when:
        - Page loads content dynamically with JavaScript
        - Need to wait for specific elements to appear
        - Content renders after page load (SPAs, React apps)
        - Goodreads, Amazon, or other modern websites
        
        Parameters:
        - url: Target webpage URL
        - wait_selector: CSS selector to wait for (optional, e.g., '.book-item')
        - timeout: Max wait time in seconds (default: 10)
        
        Returns: Page content after dynamic elements have loaded
        
        Example:
        browse_and_wait(url="https://www.goodreads.com/book/popular_by_date/2024/10", wait_selector=".bookTitle", timeout=15)
        """
    
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters."""
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url", "")
        if not url or not isinstance(url, str):
            return False
        
        if not url.startswith(("http://", "https://")):
            return False
        
        return True
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """Execute browse with wait logic."""
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        wait_selector = kwargs.get("wait_selector")
        timeout = kwargs.get("timeout", 10)
        
        # Validate required parameters
        if not url or not isinstance(url, str):
            return ToolResult(
                success=False,
                error="URL is required and must be a string",
                metadata={}
            )
        
        if self.logger:
            self.logger.status(f"Browsing {url} with wait...")
            if wait_selector:
                self.logger.status(f"Waiting for selector: {wait_selector}")
        
        try:
            # Use asyncio to run async scraping
            content = asyncio.run(self._scrape_with_wait(url, wait_selector, timeout))
            
            if self.logger:
                self.logger.status(f"Content loaded: {len(content)} characters")
            
            return ToolResult(
                success=True,
                data=content,
                metadata={
                    "url": url,
                    "wait_selector": wait_selector,
                    "timeout": timeout,
                    "content_length": len(content)
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to browse with wait: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"url": url}
            )
    
    async def _scrape_with_wait(self, url: str, wait_selector: Optional[str], timeout: int) -> str:
        """Async scraping with wait logic using Playwright."""
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Connect to Browserless
            if self.browserless_token:
                browser = await p.chromium.connect_over_cdp(
                    f"wss://production-sfo.browserless.io?token={self.browserless_token}"
                )
            else:
                # Fallback to local browser
                browser = await p.chromium.launch()
            
            try:
                page = await browser.new_page()
                
                # Navigate to URL
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                
                # Wait for specific selector if provided
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=timeout * 1000)
                    except Exception as e:
                        print(f"[BROWSE_WAIT] Selector '{wait_selector}' not found: {e}")
                        # Continue anyway, might still get content
                
                # Additional wait for any pending animations/renders
                await page.wait_for_timeout(2000)
                
                # Extract content
                content = await page.content()
                
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e


class BrowseWithScrollTool(BaseTool):
    """Tool for browsing pages with infinite scroll."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_with_scroll"
    
    @property
    def description(self) -> str:
        return """Browse a webpage with infinite scroll functionality.
        
        Use this for pages that load more content as you scroll down.
        
        Parameters:
        - url: Target webpage URL
        - scroll_times: Number of scrolls (default: 3)
        - wait_between: Wait between scrolls in ms (default: 1000)
        
        Returns: Page content after all scrolling
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        url = kwargs.get("url", "")
        return bool(url and url.startswith(("http://", "https://")))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        scroll_times = kwargs.get("scroll_times", 3)
        wait_between = kwargs.get("wait_between", 1000)
        
        # Validate required parameters
        if not url or not isinstance(url, str):
            return ToolResult(
                success=False,
                error="URL is required and must be a string",
                metadata={}
            )
        
        try:
            content = asyncio.run(self._scrape_with_scroll(url, scroll_times, wait_between))
            
            return ToolResult(
                success=True,
                data=content,
                metadata={"url": url, "scrolls": scroll_times}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"url": url}
            )
    
    async def _scrape_with_scroll(self, url: str, scroll_times: int, wait_between: int) -> str:
        """Scrape with scrolling."""
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            if self.browserless_token:
                browser = await p.chromium.connect_over_cdp(
                    f"wss://production-sfo.browserless.io?token={self.browserless_token}"
                )
            else:
                browser = await p.chromium.launch()
            
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                
                # Scroll multiple times
                for i in range(scroll_times):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(wait_between)
                
                content = await page.content()
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e


class BrowseWithClickTool(BaseTool):
    """Tool for browsing pages with clickable elements."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_with_click"
    
    @property
    def description(self) -> str:
        return """Browse and click elements to reveal content.
        
        Use for "Load More", "Show All", pagination buttons.
        
        Parameters:
        - url: Target URL
        - click_selector: CSS selector of element to click
        - wait_after: Seconds to wait after click (default: 2)
        
        Returns: Page content after clicking
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        url = kwargs.get("url", "")
        selector = kwargs.get("click_selector", "")
        return bool(url and selector)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        click_selector = kwargs.get("click_selector")
        wait_after = kwargs.get("wait_after", 2)
        
        # Validate required parameters
        if not url or not isinstance(url, str):
            return ToolResult(
                success=False,
                error="URL is required and must be a string",
                metadata={}
            )
        
        if not click_selector or not isinstance(click_selector, str):
            return ToolResult(
                success=False,
                error="click_selector is required and must be a string",
                metadata={"url": url}
            )
        
        try:
            content = asyncio.run(self._scrape_with_click(url, click_selector, wait_after))
            
            return ToolResult(
                success=True,
                data=content,
                metadata={"url": url, "clicked": click_selector}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"url": url}
            )
    
    async def _scrape_with_click(self, url: str, click_selector: str, wait_after: int) -> str:
        """Scrape with clicking."""
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            if self.browserless_token:
                browser = await p.chromium.connect_over_cdp(
                    f"wss://production-sfo.browserless.io?token={self.browserless_token}"
                )
            else:
                browser = await p.chromium.launch()
            
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                
                # Click element
                await page.click(click_selector)
                await page.wait_for_timeout(wait_after * 1000)
                
                content = await page.content()
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e
    
    def as_langchain_tool(self):
        """Convert to LangChain tool."""
        tool_instance = self
        
        @tool(args_schema=BrowseWithClickInput)
        def browse_with_click(url: str, click_selector: str, wait_after: int = 2) -> str:
            """Browse and click elements to reveal content."""
            result = tool_instance.execute(url=url, click_selector=click_selector, wait_after=wait_after)
            return tool_instance.format_result(result)
        
        return browse_with_click
