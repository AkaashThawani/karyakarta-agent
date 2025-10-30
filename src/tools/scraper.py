"""
Web Scraping Tools - Multi-Tier Fallback System

IMPLEMENTATION STATUS: ✅ IMPLEMENTED (with fallbacks)

Web scraping tool with automatic fallback strategies:
1. Browserless Cloud (if accessible)
2. Local Playwright browser (development)
3. Simple HTTP requests (static sites)

Usage:
    from src.tools.scraper import ScraperTool
    from src.services.logging_service import LoggingService
    from src.core.config import settings

    logger = LoggingService(settings.logging_url)
    scraper = ScraperTool(logger, settings)

    # Use as LangChain tool
    tool = scraper.as_langchain_tool()
"""

from typing import Optional
import time
import random
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from src.core.config import Settings
from src.utils.helpers import compress_and_chunk_content, smart_compress
from src.core.memory import get_memory_service


# Anti-bot measures
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

STEALTH_SCRIPT = """
() => {
    // Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    
    // Fix Chrome detection
    window.chrome = {
        runtime: {}
    };
    
    // Fix permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    
    // Add real plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    
    // Fix languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });
}
"""


class ScraperInput(BaseModel):
    """Input schema for web scraper tool."""
    url: str = Field(
        description="The URL of the website to scrape. Must be a valid HTTP or HTTPS URL. Example: 'https://www.apple.com/iphone'"
    )


class ScraperTool(BaseTool):
    """
    Multi-tier web scraping tool with automatic fallbacks.

    Tries methods in order:
    1. Browserless Cloud (best for JS-heavy sites)
    2. Local Playwright (development fallback)
    3. Simple HTTP requests (fast, works for static sites)
    """

    def __init__(self, session_id: str, logger: Optional[LoggingService] = None, settings: Optional[Settings] = None):
        """
        Initialize the scraper tool.

        Args:
            session_id: Current session ID (for chunk storage)
            logger: Optional logging service
            settings: Settings object with browserless config
        """
        super().__init__(logger)
        self.session_id = session_id
        self.memory_service = get_memory_service()

        if settings:
            self.browserless_api_key = settings.browserless_api_key
            self.timeout = settings.scraper_timeout
        else:
            import os
            self.browserless_api_key = os.getenv("BROWSERLESS_API_KEY")
            self.timeout = 3000

        # Browserless endpoints to try (in order)
        self.browserless_endpoints = [
            f"wss://production-sfo.browserless.io?token={self.browserless_api_key}",
        ]

    @property
    def name(self) -> str:
        """Tool name for LangChain."""
        return "browse_website"

    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """Use this tool to browse websites and extract their content.

        Use this when you need to:
        - Get the content of a specific webpage
        - Read information from a website
        - Extract text from a URL

        Input: A valid HTTP or HTTPS URL (e.g., 'https://www.example.com')
        Output: The webpage content

        Example: browse_website(url="https://www.apple.com/iphone")

        This tool automatically handles JavaScript-rendered sites and has multiple fallback methods.
        """

    def validate_params(self, **kwargs) -> bool:
        """Validate that url parameter is provided."""
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]

        if "url" not in kwargs:
            return False
        url = kwargs["url"]
        return isinstance(url, str) and len(url) > 0 and url.startswith(("http://", "https://"))

    def _scrape_with_browserless(self, url: str) -> str:
        """
        Tier 1: Try scraping with Browserless Cloud.
        Attempts multiple endpoints with fast-fail on immediate errors.
        Returns raw HTML content.
        """
        print(f"\n[SCRAPER TIER 1] Trying Browserless Cloud...")

        for endpoint in self.browserless_endpoints:
            try:
                print(f"[TIER 1] Attempting endpoint: {endpoint[:60]}...")

                with sync_playwright() as p:
                    # Reduced timeout from 10s to 5s for faster fallback
                    browser = p.chromium.connect_over_cdp(
                        f"wss://production-sfo.browserless.io?token={self.browserless_api_key}")
                    print("[BROWSER]",browser.is_connected())
                    page = browser.new_page()
                    print("[PAGE]",page.title())
                    page.goto(url, timeout=self.timeout,
                              wait_until="domcontentloaded")
                    content = page.content()
                    browser.close()

                    print(
                        f"[TIER 1] ✅ Success! Content length: {len(content)}")
                    return content
            except PlaywrightError as e:
                error_msg = str(e).lower()
                print(f"[TIER 1] ❌ Failed: {str(e)[:100]}")

                # Fast-fail conditions - these errors mean Browserless is unavailable
                # Skip to next tier immediately instead of trying other endpoints
                fast_fail_indicators = [
                    'connection refused',
                    'econnrefused',
                    'unauthorized',
                    'authentication',
                    'invalid token',
                    'dns',
                    'name resolution',
                    'network unreachable'
                ]

                if any(indicator in error_msg for indicator in fast_fail_indicators):
                    print(
                        f"[TIER 1] 🚫 Fast-fail: Service unavailable, skipping to next tier")
                    raise Exception(f"Browserless unavailable: {str(e)[:50]}")

                # For other errors (like timeout), try next endpoint
                continue
            except Exception as e:
                print(f"[TIER 1] ❌ Unexpected error: {str(e)[:100]}")
                continue

        raise Exception("All Browserless endpoints failed")

    def _scrape_with_local_browser(self, url: str) -> str:
        """
        Tier 2: Try scraping with local Playwright browser.
        Good for development and when Browserless is unavailable.
        Returns raw HTML content.
        """
        print(f"\n[SCRAPER TIER 2] Trying Local Playwright Browser...")

        try:
            # Random delay to avoid rate limiting (1-3 seconds)
            delay = random.uniform(1, 3)
            print(f"[TIER 2] Anti-bot: Waiting {delay:.1f}s...")
            time.sleep(delay)
            
            with sync_playwright() as p:
                # Pick random user agent
                user_agent = random.choice(USER_AGENTS)
                
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                
                context = browser.new_context(
                    user_agent=user_agent,
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                page = context.new_page()
                
                # Apply stealth script
                page.add_init_script(STEALTH_SCRIPT)
                
                page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
                content = page.content()
                browser.close()

                print(f"[TIER 2] ✅ Success! Content length: {len(content)}")
                return content
        except Exception as e:
            print(f"[TIER 2] ❌ Failed: {str(e)[:100]}")
            raise

    def _scrape_with_requests(self, url: str) -> str:
        """
        Tier 3: Try scraping with simple HTTP requests.
        Fast and reliable for static sites.
        Returns raw HTML content.
        """
        print(f"\n[SCRAPER TIER 3] Trying Simple HTTP Request...")

        try:
            # Random delay to avoid rate limiting (0.5-2 seconds)
            delay = random.uniform(0.5, 2)
            print(f"[TIER 3] Anti-bot: Waiting {delay:.1f}s...")
            time.sleep(delay)
            
            # Pick random user agent
            user_agent = random.choice(USER_AGENTS)
            
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            content = response.text

            print(f"[TIER 3] ✅ Success! Content length: {len(content)}")
            return content
        except Exception as e:
            print(f"[TIER 3] ❌ Failed: {str(e)[:100]}")
            raise

    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Execute web scraping with automatic fallback.

        Tries methods in order:
        1. Browserless Cloud
        2. Local Playwright browser
        3. Simple HTTP requests

        Returns first successful result.
        """
        # Handle nested kwargs from LangChain
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
            kwargs = kwargs["kwargs"]

        url = kwargs.get("url")

        # Type guard
        if not url or not isinstance(url, str):
            return ToolResult(
                success=False,
                error="URL parameter is required and must be a string",
                metadata=kwargs
            )

        print(f"\n{'='*70}")
        print(f"🌐 SCRAPER TOOL CALLED - Multi-Tier Fallback")
        print(f"{'='*70}")
        print(f"Target URL: {url}")

        if self.logger:
            self.logger.status(f"Scraping website: {url}")

        # Try all tiers to get raw HTML
        raw_html = None
        method_used = None

        # Tier 1: Try Browserless Cloud
        try:
            raw_html = self._scrape_with_browserless(url)
            method_used = "browserless"
        except Exception as e:
            print(f"[FALLBACK] Browserless failed, trying local browser...")
            if self.logger:
                self.logger.thinking(
                    f"Browserless unavailable, using fallback")

        # Tier 2: Try Local Playwright Browser
        if raw_html is None:
            try:
                raw_html = self._scrape_with_local_browser(url)
                method_used = "local_browser"
            except Exception as e:
                print(f"[FALLBACK] Local browser failed, trying HTTP request...")
                if self.logger:
                    self.logger.thinking(
                        f"Local browser failed, using HTTP fallback")

        # Tier 3: Try Simple HTTP Request
        if raw_html is None:
            try:
                raw_html = self._scrape_with_requests(url)
                method_used = "http_request"
            except Exception as e:
                print(f"[FAILED] All scraping methods failed")
                print(f"{'='*70}\n")

                error_msg = f"Failed to scrape {url}. All methods failed. Last error: {str(e)}"
                if self.logger:
                    self.logger.error(error_msg)

                return ToolResult(
                    success=False,
                    error=error_msg,
                    metadata={"url": url, "all_methods_failed": True}
                )

        # Use smart compression with token control
        print(f"\n[COMPRESSION] Processing scraped content...")
        print(f"[COMPRESSION] Original size: {len(raw_html)} characters")

        # Use smart_compress for universal content handling
        try:
            compressed_content = smart_compress(raw_html, max_tokens=1500)
            print(
                f"[COMPRESSION] Compressed size: {len(compressed_content)} characters")
            print(
                f"[COMPRESSION] Compression ratio: {(1 - len(compressed_content)/len(raw_html)) * 100:.1f}%")

            # Smart compression always returns single result
            if self.logger:
                self.logger.status(
                    f"Successfully scraped {url} using {method_used}")

            print(f"{'='*70}\n")

            return ToolResult(
                success=True,
                data=compressed_content,
                metadata={
                    "url": url,
                    "method": method_used,
                    "format": "smart_compress",
                    "total_chunks": 1,
                    "original_size": len(raw_html),
                    "compressed_size": len(compressed_content),
                    "max_tokens": 1500
                }
            )
        except Exception as e:
            print(
                f"[COMPRESSION] Smart compress failed: {e}, falling back to chunking")

        # Fallback to standard compression with chunking if smart_compress fails
        result = compress_and_chunk_content(raw_html, chunk_size=50000)

        print(
            f"[COMPRESSION] Compressed size: {result['compressed_size']} characters")
        print(
            f"[COMPRESSION] Compression ratio: {result['compression_ratio']}")
        print(f"[COMPRESSION] Total chunks: {result['total_chunks']}")

        # Store chunks if more than one
        if result['total_chunks'] > 1:
            print(
                f"[COMPRESSION] Storing {result['total_chunks']} chunks in memory...")
            self.memory_service.store_content_chunks(
                self.session_id, result['chunks'])

            # Return first chunk with metadata
            first_chunk = result['chunks'][0]
            message = f"{first_chunk}\n\n--- Content Split ---\nThis content was split into {result['total_chunks']} chunks due to size. Use get_next_chunk() to read more."

            if self.logger:
                self.logger.status(
                    f"Successfully scraped {url} using {method_used}. Content split into {result['total_chunks']} chunks.")

            print(f"{'='*70}\n")

            return ToolResult(
                success=True,
                data=message,
                metadata={
                    "url": url,
                    "method": method_used,
                    "total_chunks": result['total_chunks'],
                    "chunk_number": 1,
                    "original_size": result['original_size'],
                    "compressed_size": result['compressed_size']
                }
            )
        else:
            # Single chunk - return directly
            if self.logger:
                self.logger.status(
                    f"Successfully scraped {url} using {method_used}")

            print(f"{'='*70}\n")

            return ToolResult(
                success=True,
                data=result['chunks'][0],
                metadata={
                    "url": url,
                    "method": method_used,
                    "total_chunks": 1,
                    "original_size": result['original_size'],
                    "compressed_size": result['compressed_size']
                }
            )

    def as_langchain_tool(self):
        """Convert to LangChain tool with proper schema."""
        tool_instance = self

        @tool(args_schema=ScraperInput)
        def browse_website(url: str) -> str:
            """Use this tool to browse websites and extract their content. Provide a valid HTTP or HTTPS URL."""
            result = tool_instance.execute(url=url)
            return tool_instance.format_result(result)

        return browse_website
