"""
Universal Playwright Tool - Dynamic Method Execution

A comprehensive wrapper that exposes ALL Playwright Page methods as callable
agent tools. This allows the agent to use the full Playwright API dynamically.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from src.routing.selector_map import get_selector_map
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
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
        
        # Initialize persistent event loop for this session
        if session_id not in UniversalPlaywrightTool._event_loops:
            # Create new event loop
            loop = asyncio.new_event_loop()
            UniversalPlaywrightTool._event_loops[session_id] = loop
            
            # Start thread to run the loop
            thread = threading.Thread(target=self._run_loop_forever, args=(loop,), daemon=True)
            thread.start()
            UniversalPlaywrightTool._loop_threads[session_id] = thread
            
            print(f"[PLAYWRIGHT] Created persistent event loop for session: {session_id}")
        
        # Use class-level storage for browser persistence
        if session_id not in UniversalPlaywrightTool._browser_instances:
            UniversalPlaywrightTool._browser_instances[session_id] = None
            UniversalPlaywrightTool._page_instances[session_id] = None
            UniversalPlaywrightTool._playwright_instances[session_id] = None
    
    @staticmethod
    def _run_loop_forever(loop):
        """Run event loop forever in background thread."""
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    def run_async(self, coro):
        """Submit coroutine to persistent event loop and wait for result."""
        loop = UniversalPlaywrightTool._event_loops.get(self.session_id)
        if not loop:
            raise RuntimeError(f"No event loop found for session {self.session_id}")
        
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    
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
        
        # Resolve selector from hint if provided
        if selector_hint and not selector:
            print(f"[PLAYWRIGHT] Resolving selector hint: {selector_hint}")
            selector_map = get_selector_map()
            selectors = selector_map.get_selectors(selector_hint)
            
            if not selectors:
                print(f"[PLAYWRIGHT] No selectors found for hint '{selector_hint}', using hint as-is")
                selector = selector_hint
            else:
                # Will try multiple selectors with adaptive retry
                selector = selectors  # Pass list to try sequentially
        
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
        
        # Adaptive retry logic for selector-based methods
        if selector and isinstance(selector, list):
            # Try each selector in the list with SHORT timeout
            last_error = None
            for i, sel in enumerate(selector):
                try:
                    print(f"[PLAYWRIGHT] Trying selector {i+1}/{len(selector)}: {sel}")
                    # Use 3 second timeout for each selector attempt
                    result = await self._call_page_method(method, sel, args, url, timeout=3000)
                    
                    # Success! Promote this selector in the map
                    if selector_hint:
                        selector_map = get_selector_map()
                        selector_map.promote_selector(selector_hint, sel)
                        print(f"[PLAYWRIGHT] ✅ Selector worked! Promoted '{sel}' for hint '{selector_hint}'")
                    
                    return result
                except Exception as e:
                    print(f"[PLAYWRIGHT] ❌ Selector {i+1} failed: {sel}")
                    last_error = e
                    continue
            
            # All selectors failed
            raise Exception(f"All {len(selector)} selectors failed. Last error: {str(last_error)}")
        else:
            # Single selector or no selector - use default timeout (30s)
            result = await self._call_page_method(method, selector, args, url)
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
                    print(f"[PLAYWRIGHT] Using local Chromium with CDP")
                    self._browser = await playwright.chromium.launch(
                        headless=False,
                        args=['--remote-debugging-port=9222']
                    )
                    cdp_url = 'http://localhost:9222'
                
                self._page = await self._browser.new_page()
                print(f"[PLAYWRIGHT] ✅ Browser created successfully - browser={self._browser is not None}, page={self._page is not None}")
                
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
        else:
            print(f"[PLAYWRIGHT] ✅ Reusing existing browser for session: {self.session_id}")
            print(f"[PLAYWRIGHT] Browser state - browser={self._browser is not None}, page={self._page is not None}")
    
    async def _call_page_method(self, method: str, selector: Optional[str], args: Dict[str, Any], url: Optional[str] = None, timeout: Optional[int] = None) -> Any:
        """Dynamically call a Playwright Page method."""
        print(f"[PLAYWRIGHT] Calling method: {method}")
        print(f"[PLAYWRIGHT] Browser state BEFORE call - browser={self._browser is not None}, page={self._page is not None}")
        
        if self._page is None:
            error = f"Page is None! Cannot call {method}"
            print(f"[PLAYWRIGHT] ERROR: {error}")
            if self.logger:
                self.logger.error(f"❌ {error}")
            raise ValueError(error)
        
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
                # Playwright Response object
                return {
                    "success": True,
                    "url": result.url,
                    "status": result.status if hasattr(result, 'status') else 200,
                    "ok": result.ok if hasattr(result, 'ok') else True,
                    "message": f"Successfully navigated to {result.url}"
                }
            # For other complex objects, return string representation
            return str(result)
    
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
