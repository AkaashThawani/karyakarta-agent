"""
Universal Playwright Tool - Dynamic Method Execution

A comprehensive wrapper that exposes ALL Playwright Page methods as callable
agent tools. This allows the agent to use the full Playwright API dynamically.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from urllib.parse import urlparse
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from src.routing.selector_map import get_selector_map
from src.tools.element_parser import ElementParser
import asyncio
import threading
import json
import os


class PlaywrightExecuteInput(BaseModel):
    """Input schema for universal Playwright execution."""
    url: Optional[str] = Field(
        default=None,
        description="URL to navigate to (required for starting a new session)"
    )
    method: str = Field(
        description="Playwright Page method to execute (e.g., 'click', 'fill', 'goto', 'screenshot')"
    )
    selector: Optional[str] = Field(
        default=None,
        description="CSS selector for element-based methods (use this OR selector_hint, not both)"
    )
    selector_hint: Optional[str] = Field(
        default=None,
        description="Semantic selector hint (e.g., 'search_input', 'login_button') - preferred over raw selector"
    )
    args: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional arguments for the method as key-value pairs"
    )
    close_after: Optional[bool] = Field(
        default=False,
        description="Whether to close browser after execution"
    )


class UniversalPlaywrightTool(BaseTool):
    """
    Universal Playwright Tool - Execute any Playwright Page method.
    
    This tool provides a unified interface to the entire Playwright API,
    allowing the agent to call any Page method dynamically.
    
    Supported methods include (but not limited to):
    - Navigation: goto, go_back, go_forward, reload
    - Interaction: click, fill, press, hover, check, uncheck
    - Content: content, inner_text, inner_html, text_content
    - Screenshots: screenshot
    - Evaluation: evaluate, evaluate_handle
    - Waiting: wait_for_selector, wait_for_load_state, wait_for_timeout
    - And many more from the Playwright Page API
    """
    
    # Class-level storage to persist across instances
    _browser_instances = {}
    _page_instances = {}
    _playwright_instances = {}
    _event_loops = {}
    _loop_threads = {}
    _stop_flags = {}  # Track when to stop event loops
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
        self._last_url = None  # Track URL changes for auto-learning
        
        # Initialize persistent event loop for this session
        if session_id not in UniversalPlaywrightTool._event_loops:
            # Create new event loop
            loop = asyncio.new_event_loop()
            UniversalPlaywrightTool._event_loops[session_id] = loop
            UniversalPlaywrightTool._stop_flags[session_id] = False
            
            # Start thread to run the loop
            thread = threading.Thread(target=self._run_loop_forever, args=(loop, session_id), daemon=True)
            thread.start()
            UniversalPlaywrightTool._loop_threads[session_id] = thread
            
            print(f"[PLAYWRIGHT] Created persistent event loop for session: {session_id}")
        
        # Use class-level storage for browser persistence
        if session_id not in UniversalPlaywrightTool._browser_instances:
            UniversalPlaywrightTool._browser_instances[session_id] = None
            UniversalPlaywrightTool._page_instances[session_id] = None
            UniversalPlaywrightTool._playwright_instances[session_id] = None
    
    @staticmethod
    def _run_loop_forever(loop, session_id):
        """Run event loop until stop is requested."""
        asyncio.set_event_loop(loop)
        try:
            # Run until stop flag is set
            async def wait_for_stop():
                while not UniversalPlaywrightTool._stop_flags.get(session_id, False):
                    await asyncio.sleep(0.1)
            
            loop.run_until_complete(wait_for_stop())
        except Exception as e:
            print(f"[PLAYWRIGHT] Event loop error for {session_id}: {e}")
        finally:
            print(f"[PLAYWRIGHT] Event loop stopped for {session_id}")
    
    def run_async(self, coro):
        """Submit coroutine to persistent event loop and wait for result."""
        loop = UniversalPlaywrightTool._event_loops.get(self.session_id)
        if not loop:
            raise RuntimeError(f"No event loop found for session {self.session_id}")
        
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    
    @classmethod
    def stop_all_loops(cls):
        """Stop all event loops gracefully."""
        print("[PLAYWRIGHT] Stopping all event loops...")
        for session_id in list(cls._stop_flags.keys()):
            cls._stop_flags[session_id] = True
            print(f"[PLAYWRIGHT] Signaled stop for session: {session_id}")
        
        # Wait for threads to finish (with timeout)
        import time
        max_wait = 2.0  # 2 seconds max
        start_time = time.time()
        
        for session_id, thread in list(cls._loop_threads.items()):
            remaining = max_wait - (time.time() - start_time)
            if remaining > 0 and thread.is_alive():
                thread.join(timeout=remaining)
                if not thread.is_alive():
                    print(f"[PLAYWRIGHT] Thread stopped for session: {session_id}")
                else:
                    print(f"[PLAYWRIGHT] Thread timeout for session: {session_id}")
        
        print("[PLAYWRIGHT] All event loops stopped")
    
    @classmethod
    async def cleanup_session(cls, session_id: str):
        """
        Cleanup all resources for a specific session.
        Called when a task times out or is cancelled.
        
        Args:
            session_id: Session ID to cleanup
        """
        print(f"[PLAYWRIGHT] Cleaning up session: {session_id}")
        
        try:
            # Close browser if exists
            browser = cls._browser_instances.get(session_id)
            if browser:
                try:
                    print(f"[PLAYWRIGHT] Closing browser for session: {session_id}")
                    await asyncio.wait_for(browser.close(), timeout=5.0)
                    print(f"[PLAYWRIGHT] ✅ Browser closed: {session_id}")
                except asyncio.TimeoutError:
                    print(f"[PLAYWRIGHT] ⚠️ Browser close timeout: {session_id}")
                except Exception as e:
                    print(f"[PLAYWRIGHT] Error closing browser: {e}")
            
            # Stop playwright instance
            playwright = cls._playwright_instances.get(session_id)
            if playwright:
                try:
                    print(f"[PLAYWRIGHT] Stopping Playwright for session: {session_id}")
                    await playwright.stop()
                    print(f"[PLAYWRIGHT] ✅ Playwright stopped: {session_id}")
                except Exception as e:
                    print(f"[PLAYWRIGHT] Error stopping Playwright: {e}")
            
            # Stop event loop
            if session_id in cls._stop_flags:
                cls._stop_flags[session_id] = True
                print(f"[PLAYWRIGHT] Signaled event loop stop: {session_id}")
            
            # Wait for thread to finish (with timeout)
            thread = cls._loop_threads.get(session_id)
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
                if not thread.is_alive():
                    print(f"[PLAYWRIGHT] ✅ Thread stopped: {session_id}")
                else:
                    print(f"[PLAYWRIGHT] ⚠️ Thread didn't stop: {session_id}")
            
            # Clear all references
            cls._browser_instances.pop(session_id, None)
            cls._page_instances.pop(session_id, None)
            cls._playwright_instances.pop(session_id, None)
            cls._event_loops.pop(session_id, None)
            cls._loop_threads.pop(session_id, None)
            cls._stop_flags.pop(session_id, None)
            
            print(f"[PLAYWRIGHT] ✅ Session cleanup complete: {session_id}")
            
        except Exception as e:
            print(f"[PLAYWRIGHT] Error during session cleanup: {e}")
            import traceback
            traceback.print_exc()
    
    @property
    def _browser(self):
        return UniversalPlaywrightTool._browser_instances.get(self.session_id)
    
    @_browser.setter
    def _browser(self, value):
        UniversalPlaywrightTool._browser_instances[self.session_id] = value
    
    @property
    def _page(self):
        return UniversalPlaywrightTool._page_instances.get(self.session_id)
    
    @_page.setter
    def _page(self, value):
        UniversalPlaywrightTool._page_instances[self.session_id] = value
    
    @property
    def name(self) -> str:
        return "playwright_execute"
    
    @property
    def description(self) -> str:
        return """Execute any Playwright Page method dynamically.
        
        This universal tool provides access to the complete Playwright API.
        You can execute ANY Playwright Page method by specifying:
        - method: The Playwright method name
        - selector: CSS selector (if needed for element methods)
        - args: Additional arguments as key-value pairs
        
        Common Methods:
        
        NAVIGATION:
        - goto: Navigate to URL
        - go_back: Go back in history
        - go_forward: Go forward in history
        - reload: Reload page
        
        INTERACTION:
        - click: Click element
        - fill: Fill input field
        - press: Press keyboard key
        - hover: Hover over element
        - check: Check checkbox
        - uncheck: Uncheck checkbox
        - select_option: Select dropdown option
        
        CONTENT EXTRACTION:
        - content: Get full HTML
        - inner_text: Get element text
        - inner_html: Get element HTML
        - text_content: Get text content
        - get_attribute: Get element attribute
        
        SCREENSHOTS:
        - screenshot: Take screenshot (returns base64)
        
        WAITING:
        - wait_for_selector: Wait for element
        - wait_for_load_state: Wait for page load
        - wait_for_timeout: Wait for time
        
        EVALUATION:
        - evaluate: Execute JavaScript
        
        Example Usage:
        1. Navigate: method="goto", args={"url": "https://example.com"}
        2. Click: method="click", selector="button.submit"
        3. Fill: method="fill", selector="input[name='email']", args={"value": "test@example.com"}
        4. Screenshot: method="screenshot", args={"path": "screenshot.png", "full_page": True}
        5. Get text: method="inner_text", selector="h1"
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        method = kwargs.get("method")
        return bool(method and isinstance(method, str))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        method = kwargs.get("method")
        selector = kwargs.get("selector")
        selector_hint = kwargs.get("selector_hint")
        args = kwargs.get("args", {})
        close_after = kwargs.get("close_after", False)
        
        if not method:
            return ToolResult(
                success=False,
                error="Method is required",
                metadata={}
            )
        
        # WATERFALL SELECTOR RESOLUTION
        # 1. Check cache → 2. Element Parser → 3. Site Intelligence (LLM fallback)
        if selector_hint and not selector:
            print(f"[PLAYWRIGHT] Resolving selector hint: {selector_hint}")
            selector_map = get_selector_map()
            
            # Get URL from page if not explicitly provided
            if not url and self._page:
                url = self._page.url
                print(f"[PLAYWRIGHT] Using current page URL: {url}")
            
            # STEP 1: Check cache (O(1) lookup)
            if url:
                best_selector = selector_map.get_selector(url, "playwright_execute", selector_hint)
                
                if best_selector:
                    print(f"[PLAYWRIGHT] ✅ [CACHE] Found selector for {selector_hint}: {best_selector}")
                    selector = best_selector
                else:
                    # STEP 2: Try Element Parser (heuristic, fast, no LLM)
                    print(f"[PLAYWRIGHT] 🔍 [PARSER] Using ElementParser for {selector_hint}...")
                    
                    try:
                        # Parse page HTML
                        html = self.run_async(self._page.content()) # pyright: ignore[reportOptionalMemberAccess]
                        parser = ElementParser()
                        elements = parser.parse_page(html)
                        
                        print(f"[PLAYWRIGHT] Extracted {len(elements)} interactive elements")
                        
                        # Find matching element
                        match = parser.find_element(elements, selector_hint)
                        
                        if match:
                            selector = match['selector']
                            print(f"[PLAYWRIGHT] ✅ [PARSER] Found selector: {selector}")
                            
                            # Cache for future use
                            parsed = urlparse(url) # pyright: ignore[reportUnboundVariable]
                            domain = parsed.netloc or parsed.path
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            path = parsed.path or "/"
                            
                            selector_map.save_page_action_selector(domain, path, selector_hint, selector)
                            
                            # Also save elements for tree building
                            selector_map.save_page_elements(domain, path, url, elements)
                        else:
                            # STEP 3: Site Intelligence (LLM fallback)
                            print(f"[PLAYWRIGHT] ⚠️ [PARSER] No match, falling back to Site Intelligence...")
                    except Exception as parser_error:
                        print(f"[PLAYWRIGHT] Element Parser error: {parser_error}")
                    
                    # If parser didn't find anything, try Site Intelligence
                    if not selector or selector == selector_hint:
                        try:
                            # Import Site Intelligence Tool
                            from src.tools.site_intelligence import SiteIntelligenceTool
                            from src.services.llm_service import LLMService
                            from src.core.config import settings
                            
                            # Initialize Site Intelligence
                            intelligence = SiteIntelligenceTool(self.session_id, self.logger)
                            
                            # Get LLM service with settings
                            llm_service = LLMService(settings)
                            
                            # Learn site structure
                            print(f"[PLAYWRIGHT] Learning site structure for {url}...")
                            schema = self.run_async(intelligence.learn_site(url, self._page, llm_service))
                            
                            # Try to get selector from learned schema
                            parsed_url = urlparse(url) # pyright: ignore[reportUnboundVariable]
                            domain = parsed_url.netloc or parsed_url.path
                            if domain.startswith('www.'):
                                domain = domain[4:]
                            
                            learned_selector = intelligence.get_element_selector(domain, selector_hint)
                            
                            if learned_selector:
                                print(f"[PLAYWRIGHT] ✅ [LLM] Learned selector: {learned_selector}")
                                selector = learned_selector
                            else:
                                print(f"[PLAYWRIGHT] ⚠️ [LLM] Couldn't find selector for '{selector_hint}'")
                                # Fall back to using hint as-is
                                selector = selector_hint
                                
                        except Exception as e:
                            print(f"[PLAYWRIGHT] Site Intelligence failed: {e}")
                            # Fall back to using hint as-is
                            selector = selector_hint
            else:
                # No URL provided, use backward compatible method
                selectors = selector_map.get_selectors(selector_hint)
                if selectors:
                    selector = selectors
                else:
                    selector = selector_hint
        
        # AUTO-LEARNING: Even with direct selector, check if site is in map
        # If site is unmapped, trigger Site Intelligence to learn it
        if selector and not selector_hint:
            # Get URL from page if not explicitly provided
            current_url = url if url else (self._page.url if self._page else None)
            
            if current_url:
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                domain = parsed.netloc or parsed.path
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                # Check if domain exists in selector map
                selector_map = get_selector_map()
                
                # Check if we have any cached data for this domain
                cache_file = selector_map.cache_dir / f"{domain}.json"
                
                if not cache_file.exists():
                    # DISABLED: Site Intelligence auto-learning
                    # TODO: Re-enable after fixing "Extra data" JSON parsing
                    print(f"[PLAYWRIGHT] ⚠️ Site Intelligence disabled - skipping auto-learn for '{domain}'")
        
        if self.logger:
            self.logger.status(f"Executing Playwright method: {method}")
        
        try:
            # Use persistent event loop via run_async
            result = self.run_async(
                self._execute_playwright_method(url, method, selector, selector_hint, args, close_after)
            )
            
            if self.logger:
                self.logger.status(f"Playwright method '{method}' completed successfully")
            
            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "method": method,
                    "selector": selector if isinstance(selector, str) else "multiple",
                    "selector_hint": selector_hint,
                    "url": url
                }
            )
            
        except Exception as e:
            error_msg = f"Playwright execution failed: {str(e)}"
            # Don't log to UI - let executor handle final error after retries
            # if self.logger:
            #     self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={"method": method}
            )
    
    async def _execute_playwright_method(
        self, 
        url: Optional[str], 
        method: str, 
        selector: Optional[Any],  # Can be str or List[str]
        selector_hint: Optional[str],
        args: Dict[str, Any],
        close_after: bool
    ) -> Any:
        """Execute the actual Playwright method with adaptive retry."""
        from playwright.async_api import async_playwright
        
        # Ensure browser is initialized
        if self._page is None:
            await self._ensure_browser()
        
        # For goto method, pass URL as first argument
        if method == "goto" and url:
            # Merge URL into args if not already there
            if "url" not in args:
                args = {"url": url, **args}
        
        # Adaptive retry logic for selector-based methods with learning
        if selector and isinstance(selector, list):
            # Try each selector in the list with SHORT timeout
            last_error = None
            import time
            
            for i, sel in enumerate(selector):
                try:
                    print(f"[PLAYWRIGHT] Trying selector {i+1}/{len(selector)}: {sel}")
                    start_time = time.time()
                    
                    # Use 3 second timeout for each selector attempt
                    result = await self._call_page_method(method, sel, args, url, timeout=3000)
                    
                    response_time = time.time() - start_time
                    
                    # Success! Promote this selector in the map with site-specific learning
                    if selector_hint and url:
                        selector_map = get_selector_map()
                        selector_map.promote_selector(
                            url=url,
                            tool="playwright_execute",
                            hint=selector_hint,
                            selector=sel,
                            success=True,
                            response_time=response_time
                        )
                        print(f"[PLAYWRIGHT] ✅ Selector worked! Promoted '{sel}' for {url}/{selector_hint} (took {response_time:.2f}s)")
                    
                    return result
                except Exception as e:
                    print(f"[PLAYWRIGHT] ❌ Selector {i+1} failed: {sel}")
                    
                    # Record failure if we have URL and hint
                    if selector_hint and url:
                        selector_map = get_selector_map()
                        selector_map.promote_selector(
                            url=url,
                            tool="playwright_execute",
                            hint=selector_hint,
                            selector=sel,
                            success=False
                        )
                    
                    last_error = e
                    continue
            
            # All selectors failed
            raise Exception(f"All {len(selector)} selectors failed. Last error: {str(last_error)}")
        else:
            # Single selector or no selector - use default timeout (30s)
            import time
            start_time = time.time()
            
            result = await self._call_page_method(method, selector, args, url)
            
            # Record success for single selector
            if selector_hint and url and isinstance(selector, str):
                response_time = time.time() - start_time
                selector_map = get_selector_map()
                selector_map.promote_selector(
                    url=url,
                    tool="playwright_execute",
                    hint=selector_hint,
                    selector=selector,
                    success=True,
                    response_time=response_time
                )
                print(f"[PLAYWRIGHT] ✅ Recorded success for '{selector}' on {url}/{selector_hint}")
            
            return result
    
    async def _ensure_browser(self):
        """Ensure browser and page are initialized."""
        from playwright.async_api import async_playwright
        
        if self._browser is None:
            print(f"[PLAYWRIGHT] Creating NEW browser for session: {self.session_id}")
            if self.logger:
                self.logger.status(f"🌐 Launching browser...")
            
            try:
                # Store playwright instance to keep it alive
                playwright = await async_playwright().start()
                UniversalPlaywrightTool._playwright_instances[self.session_id] = playwright
                
                if self.browserless_token:
                    print(f"[PLAYWRIGHT] Using Browserless (remote browser)")
                    self._browser = await playwright.chromium.connect_over_cdp(
                        f"wss://production-sfo.browserless.io?token={self.browserless_token}"
                    )
                    cdp_url = None  # Remote browser, no local CDP
                else:
                    # Read HEADLESS from environment (default to True for production)
                    headless_mode = os.getenv("HEADLESS", "true").lower() == "true"
                    print(f"[PLAYWRIGHT] Using local Chromium with CDP (headless={headless_mode})")
                    self._browser = await playwright.chromium.launch(
                        headless=headless_mode,
                        args=['--remote-debugging-port=9222']
                    )
                    cdp_url = 'http://localhost:9222'
                
                self._page = await self._browser.new_page()
                
                # Set global 10 second timeout for all operations
                self._page.set_default_timeout(10000)
                print(f"[PLAYWRIGHT] ✅ Browser created successfully with 10s timeout - browser={self._browser is not None}, page={self._page is not None}")
                
                # Notify frontend that browser is active
                if self.logger:
                    self.logger.status(f"✅ Browser ready")
                    # Send custom browser-status event
                    import requests
                    try:
                        requests.post('http://localhost:3000/api/socket/log', json={
                            'type': 'browser-status',
                            'status': 'active',
                            'cdp_url': cdp_url  # None for Browserless, URL for local
                        }, timeout=1)
                    except:
                        pass
            except Exception as e:
                error_msg = f"❌ Browser launch FAILED: {type(e).__name__}: {str(e)}"
                print(f"[PLAYWRIGHT] {error_msg}")
                if self.logger:
                    self.logger.error(error_msg)
                raise Exception(error_msg)
        # Browser already exists - no need to log every time
    
    async def _call_page_method(self, method: str, selector: Optional[str], args: Dict[str, Any], url: Optional[str] = None, timeout: Optional[int] = None) -> Any:
        """Dynamically call a Playwright Page method or custom tool method."""
        # Only log method name (removed redundant browser state logs)
        print(f"[PLAYWRIGHT] Calling method: {method}")
        
        # Special handling for custom tool methods (not Page methods)
        if method == "extract_chart":
            # This is a custom method on the tool itself
            required_fields = args.get("required_fields", [])
            if not url and self._page:
                url = self._page.url
            
            if not url:
                raise ValueError("extract_chart requires a URL")
            
            # No need to log "Calling custom extract_chart method" - already logged method name above
            return await self.extract_chart(url, required_fields)
        
        # Check if page is actually still valid
        if self._page is None:
            error = f"Page is None! Cannot call {method}"
            print(f"[PLAYWRIGHT] ERROR: {error}")
            if self.logger:
                self.logger.error(f"❌ {error}")
            raise ValueError(error)
        
        # Check if page/browser closed - clear references and recreate
        try:
            if self._page.is_closed():
                print(f"[PLAYWRIGHT] ⚠️ Page was closed, clearing references and recreating...")
                # IMPORTANT: Clear references so _ensure_browser creates NEW instances
                self._browser = None
                self._page = None
                await self._ensure_browser()
        except Exception as e:
            print(f"[PLAYWRIGHT] ⚠️ Browser/page check failed: {e}, clearing and recreating...")
            # Clear all references to force fresh creation
            self._browser = None
            self._page = None
            await self._ensure_browser()
        
        if not hasattr(self._page, method):
            raise ValueError(f"Method '{method}' not found on Playwright Page object")
        
        # Send playwright-log event BEFORE execution
        self._send_playwright_log(method, selector, args, url, status='starting')
        
        page_method = getattr(self._page, method)
        
        # Build arguments based on method signature
        call_args = []
        call_kwargs = args.copy()
        
        # Add timeout if provided (for fast selector retries)
        if timeout is not None:
            call_kwargs['timeout'] = timeout
        
        # Special handling for goto method - URL is first positional argument
        if method == "goto":
            # Get URL from args dict or url parameter
            goto_url = call_kwargs.pop("url", url)
            if not goto_url:
                raise ValueError("goto method requires a URL")
            call_args.append(goto_url)
        
        # Add selector as first argument if provided and method needs it
        elif selector:
            # Methods that take selector as first positional argument
            selector_methods = [
                'click', 'fill', 'press', 'hover', 'check', 'uncheck', 'focus',
                'get_attribute', 'inner_text', 'inner_html', 'text_content',
                'is_visible', 'is_hidden', 'is_enabled', 'is_disabled', 'is_checked',
                'wait_for_selector', 'query_selector', 'query_selector_all',
                'dispatch_event', 'select_option', 'set_input_files', 'tap', 'dblclick'
            ]
            
            if method in selector_methods:
                call_args.append(selector)
        
        # Call the method
        try:
            result = await page_method(*call_args, **call_kwargs)
            
            # Send success log
            self._send_playwright_log(method, selector, args, url, status='success')
            
            # CHECK FOR URL CHANGES - Trigger Site Intelligence on navigation
            if method in ['goto', 'click', 'press'] and self._page:
                try:
                    current_url = self._page.url
                    
                    # If URL changed and we don't have a hint, check if we should learn this page
                    if current_url != self._last_url:
                        print(f"[PLAYWRIGHT] 🔄 URL changed: {self._last_url} → {current_url}")
                        self._last_url = current_url
                        
                        # Parse new URL
                        parsed = urlparse(current_url)
                        domain = parsed.netloc or parsed.path
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        
                        # Check if we have intelligence for this page
                        selector_map = get_selector_map()
                        cache_file = selector_map.cache_dir / f"{domain}.json"
                        
                        # DISABLED: Site Intelligence after navigation
                        # TODO: Re-enable after fixing "Extra data" JSON parsing
                        if selector and not result:
                            print(f"[PLAYWRIGHT] ⚠️ Selector failed on new page, but Site Intelligence disabled")
                
                except Exception as e:
                    print(f"[PLAYWRIGHT] URL change detection error: {e}")
            
            # Handle different return types - pass context for better serialization
            return self._serialize_result(result, method, selector, args)
        except Exception as e:
            # Send failure log with error details
            print(f"[PLAYWRIGHT] ERROR in {method}: {type(e).__name__}: {str(e)}")
            self._send_playwright_log(method, selector, args, url, status='failed')
            # Re-raise with more context
            raise Exception(f"Playwright {method} failed: {type(e).__name__}: {str(e)}")
    
    def _send_playwright_log(self, method: str, selector: Optional[str], args: Dict[str, Any], url: Optional[str], status: str):
        """Send Playwright action log to frontend via WebSocket."""
        import requests
        import time
        
        # Build log message
        log_data = {
            'type': 'playwright-log',
            'method': method,
            'selector': selector,
            'url': url,
            'args': args,
            'status': status,
            'timestamp': time.time()
        }
        
        try:
            requests.post('http://localhost:3000/api/socket/log', json=log_data, timeout=1)
        except:
            pass  # Silently fail if frontend not available
    
    def _serialize_result(self, result: Any, method: Optional[str] = None, selector: Optional[str] = None, args: Optional[Dict] = None) -> Any:
        """Serialize the result to JSON-compatible format with context."""
        if result is None:
            # Return meaningful message for None results
            if method == "fill" and args:
                return {
                    "success": True,
                    "action": f"filled field",
                    "selector": selector,
                    "value": args.get("value", ""),
                    "message": f"Successfully filled field with '{args.get('value', '')}'"
                }
            elif method == "click":
                return {
                    "success": True,
                    "action": "clicked element",
                    "selector": selector,
                    "message": f"Successfully clicked element"
                }
            elif method == "press" and args:
                return {
                    "success": True,
                    "action": f"pressed key",
                    "selector": selector,
                    "key": args.get("key", ""),
                    "message": f"Successfully pressed '{args.get('key', '')}'"
                }
            else:
                return {
                    "success": True,
                    "action": method,
                    "message": f"Successfully executed {method}"
                }
        elif isinstance(result, (str, int, float, bool)):
            return result
        elif isinstance(result, bytes):
            # For screenshots, return base64
            import base64
            return base64.b64encode(result).decode('utf-8')
        elif isinstance(result, list):
            return [self._serialize_result(item, method, selector, args) for item in result]
        elif isinstance(result, dict):
            return {k: self._serialize_result(v, method, selector, args) for k, v in result.items()}
        else:
            # Check if it's a Playwright Response object
            if hasattr(result, 'url') and hasattr(result, 'status'):
                # Playwright Response object - type guard
                url_val = getattr(result, 'url', '')
                status_val = getattr(result, 'status', 200)
                ok_val = getattr(result, 'ok', True)
                return {
                    "success": True,
                    "url": url_val,
                    "status": status_val,
                    "ok": ok_val,
                    "message": f"Successfully navigated to {url_val}"
                }
            # For other complex objects, return string representation
            return str(result)
    
    async def extract_chart(
        self,
        url: str,
        required_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured chart/list data using scraping-first approach.
        
        Args:
            url: URL to extract from
            required_fields: Fields to extract (e.g., song, artist, producer)
        
        Returns:
            List of records with required fields
        """
        from src.tools.chart_extractor import PlaywrightChartExtractor
        
        # Ensure browser is ready
        await self._ensure_browser()
        
        # Type guard - ensure page exists
        if self._page is None:
            raise RuntimeError("Failed to initialize browser page")
        
        # Navigate to URL
        await self._page.goto(url)
        await self._page.wait_for_load_state("domcontentloaded")
        
        # Extract using chart extractor
        extractor = PlaywrightChartExtractor()
        records = await extractor.extract_chart(
            self._page,
            url,
            required_fields
        )
        
        return records
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=PlaywrightExecuteInput)
        def playwright_execute(
            method: str,
            url: Optional[str] = None,
            selector: Optional[str] = None,
            args: Optional[Dict[str, Any]] = None,
            close_after: Optional[bool] = False
        ) -> str:
            """Execute any Playwright Page method dynamically."""
            result = tool_instance.execute(
                url=url,
                method=method,
                selector=selector,
                args=args or {},
                close_after=close_after
            )
            return tool_instance.format_result(result)
        
        return playwright_execute


class PlaywrightSessionTool(BaseTool):
    """
    Manage Playwright browser sessions.
    
    This tool helps manage browser lifecycle:
    - Start new sessions
    - Close sessions
    - Get session status
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.sessions = {}  # Track active sessions
    
    @property
    def name(self) -> str:
        return "playwright_session"
    
    @property
    def description(self) -> str:
        return """Manage Playwright browser sessions.
        
        Operations:
        - start: Start new browser session
        - close: Close browser session
        - status: Check session status
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        operation = kwargs.get("operation")
        return bool(operation in ["start", "close", "status"])
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        operation = kwargs.get("operation")
        
        if operation == "status":
            return ToolResult(
                success=True,
                data={"active_sessions": len(self.sessions), "session_ids": list(self.sessions.keys())},
                metadata={}
            )
        
        # Placeholder for session management
        return ToolResult(
            success=True,
            data=f"Session operation '{operation}' completed",
            metadata={"operation": operation}
        )
