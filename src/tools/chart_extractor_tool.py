"""
Chart Extractor Tool - BaseTool wrapper for PlaywrightChartExtractor

Provides a tool interface for structured data extraction from webpages.
"""

from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolResult
from src.tools.chart_extractor import PlaywrightChartExtractor
from playwright.async_api import Page
import asyncio


class ChartExtractorTool(BaseTool):
    """
    Tool for extracting structured data (tables, lists, charts) from webpages.
    
    This tool wraps PlaywrightChartExtractor and provides:
    - Automatic field detection
    - Multi-layer extraction (cached, scraped, LLM fallback)
    - Completeness validation
    - Self-learning capabilities
    
    Example:
        tool = ChartExtractorTool()
        result = tool.execute(
            url="https://example.com/products",
            required_fields=["name", "price", "rating"]
        )
    """
    
    def __init__(self):
        """Initialize Chart Extractor Tool."""
        super().__init__()
        self.extractor = PlaywrightChartExtractor()
        self.partial_results = []  # Shared storage for progressive saving
        
        # NEW: Learning Manager
        try:
            from src.tools.learning_manager import get_learning_manager
            self.learning_manager = get_learning_manager()
        except Exception as e:
            print(f"[CHART_TOOL] Learning Manager not available: {e}")
            self.learning_manager = None
    
    @property
    def name(self) -> str:
        """Tool name for registration."""
        return "chart_extractor"
    
    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return "Extract structured data (tables, lists, charts) from webpages"
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        """
        Implementation required by BaseTool.
        Delegates to the main execute method.
        """
        return self.execute(**kwargs)
    
    def execute(
        self,
        url: Optional[str] = None,
        required_fields: Optional[List[str]] = None,
        page: Optional[Page] = None,
        limit: Optional[int] = None,
        requested_count: Optional[int] = None,
        task_description: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute chart extraction.
        
        Args:
            url: URL to extract from (optional if page is provided)
            required_fields: List of field names to extract
            page: Playwright page instance (if already navigated)
            limit: Maximum number of records to extract
            requested_count: Number of records expected (for completeness check)
            task_description: Original task description for context (optional)
            **kwargs: Additional parameters
            
        Returns:
            ToolResult with extracted records
        """
        # Run async extraction with proper error handling
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                # Create new event loop if none exists or closed
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Check if loop is already running (nested async context)
            if loop.is_running():
                try:
                    import nest_asyncio # type: ignore
                    nest_asyncio.apply()
                    print("[CHART_TOOL] Applied nest_asyncio for nested async context")
                except ImportError:
                    print("[CHART_TOOL] nest_asyncio not available, creating new thread")
                    # Run in a new thread to avoid nested loop issues
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            self._run_in_new_loop, 
                            url, required_fields, page, limit, 
                            requested_count, task_description, **kwargs
                        )
                        return future.result()
            
            # Run the async code
            result = loop.run_until_complete(
                self._async_execute(
                    url, required_fields, page, limit, 
                    requested_count, task_description, **kwargs
                )
            )
            
            return result
            
        except Exception as e:
            print(f"[CHART_TOOL] Execute error: {e}")
            import traceback
            traceback.print_exc()
            
            return ToolResult(
                success=False,
                error=f"Chart extraction failed: {str(e)}"
            )
    
    def _run_in_new_loop(
        self,
        url: Optional[str],
        required_fields: Optional[List[str]],
        page: Optional[Page],
        limit: Optional[int],
        requested_count: Optional[int],
        task_description: Optional[str],
        **kwargs
    ) -> ToolResult:
        """
        Run async code in a new event loop (for nested async contexts).
        
        Args:
            url: URL to extract from
            required_fields: Fields to extract
            page: Playwright page
            limit: Max records
            requested_count: Number of records expected
            task_description: Original task description
            **kwargs: Additional params
            
        Returns:
            ToolResult
        """
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(
                self._async_execute(
                    url, required_fields, page, limit,
                    requested_count, task_description, **kwargs
                )
            )
        finally:
            new_loop.close()
    
    async def _async_execute(
        self,
        url: Optional[str],
        required_fields: Optional[List[str]],
        page: Optional[Page],
        limit: Optional[int],
        requested_count: Optional[int],
        task_description: Optional[str],
        **kwargs
    ) -> ToolResult:
        """
        Async execution logic.
        
        Args:
            url: URL to extract from
            required_fields: Fields to extract
            page: Playwright page
            limit: Max records
            requested_count: Number of records expected
            task_description: Original task description
            **kwargs: Additional params
            
        Returns:
            ToolResult with extracted data
        """
        try:
            if not required_fields:
                required_fields = []
            
            # Initialize should_close flag
            should_close = False
            playwright_instance = None
            browser_instance = None
            
            # Try to get page from UniversalPlaywrightTool (persistent browser)
            if not page:
                try:
                    from src.tools.playwright_universal import UniversalPlaywrightTool
                    
                    # Try multiple common session IDs (default, global, session)
                    session_ids = ["default", "global", "session"]
                    persistent_page = None
                    
                    for session_id in session_ids:
                        persistent_page = UniversalPlaywrightTool._page_instances.get(session_id)
                        if persistent_page:
                            # Don't call is_closed() - it can block during shutdown
                            # Just try to use the page and handle errors naturally
                            print(f"[CHART_TOOL] Using persistent browser from session: {session_id}")
                            break
                    
                    if persistent_page:
                        page = persistent_page
                        
                        # Get URL from page if not provided
                        if not url and hasattr(page, 'url'):
                            url = page.url
                    else:
                        print(f"[CHART_TOOL] No persistent browser available in any session")
                        page = None
                except Exception as e:
                    print(f"[CHART_TOOL] Failed to get persistent browser: {e}")
                    page = None
            
            # If still no page, we need a URL to proceed
            if not page and not url:
                return ToolResult(
                    success=False,
                    error="Either a page or URL must be provided for extraction"
                )
            
            # Create our own browser only if absolutely necessary
            if not page and url:
                print(f"[CHART_TOOL] Creating fallback browser instance")
                from playwright.async_api import async_playwright

                playwright_instance = await async_playwright().start()
                browser_instance = await playwright_instance.chromium.launch(headless=True)
                page = await browser_instance.new_page()
                page.set_default_timeout(60000)  # 60 second timeout
                should_close = True

                # Handle URL parameter - can be string or list (take first if list)
                if isinstance(url, list):
                    if url:
                        url = url[0]  # Take first URL
                        print(f"[CHART_TOOL] Received URL list, using first: {url}")
                    else:
                        print(f"[CHART_TOOL] Received empty URL list")
                        return ToolResult(
                            success=False,
                            error="Empty URL list provided"
                        )

                if not isinstance(url, str):
                    return ToolResult(
                        success=False,
                        error=f"Invalid URL type: {type(url)}, expected string"
                    )

                # Navigate to URL
                print(f"[CHART_TOOL] Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded")  # Faster load
            
            try:
                # Ensure we have both page and URL at this point
                if not page:
                    return ToolResult(
                        success=False,
                        error="No page available for extraction"
                    )
                
                # Get current URL if not provided
                if not url and page:
                    url = page.url
                
                # Add timestamp logging
                import time
                from datetime import datetime
                
                def log_time(msg):
                    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[CHART_TOOL] ⏱️ {now} - {msg}")
                
                log_time(f"Ready to extract from {url}")
                print(f"[CHART_TOOL] Required fields: {required_fields}")
                
                # Check if page has content with timeout
                log_time("Getting page HTML...")
                start_html = time.time()
                try:
                    html = await asyncio.wait_for(page.content(), timeout=30.0)
                    html_time = time.time() - start_html
                    html_size_mb = len(html) / (1024 * 1024)
                    log_time(f"Got HTML ({html_size_mb:.2f} MB) in {html_time:.2f}s")
                except asyncio.TimeoutError:
                    html_time = time.time() - start_html
                    log_time(f"⏱️ HTML fetch timeout after {html_time:.2f}s")
                    return ToolResult(
                        success=False,
                        error=f"Failed to get page HTML after 30 seconds. Page may be too complex or have loading issues.",
                        metadata={
                            "url": url,
                            "required_fields": required_fields,
                            "html_timeout": True
                        }
                    )
                
                # Clear previous partial results
                self.partial_results = []
                
                log_time("Starting extraction...")
                
                # Extract data with 60 second timeout and progressive saving
                try:
                    start_extract = time.time()
                    # Ensure url is a string (should be by this point)
                    if not isinstance(url, str):
                        return ToolResult(
                            success=False,
                            error=f"URL must be a string, got {type(url)}"
                        )

                    records = await asyncio.wait_for(
                        self.extractor.extract_chart(
                            page=page,
                            url=url,
                            required_fields=required_fields,
                            limit=limit,  # Pass limit to extractor for early termination
                            result_storage=self.partial_results  # Pass storage for progressive saving
                        ),
                        timeout=60.0  # 60 second timeout
                    )
                    extract_time = time.time() - start_extract
                    log_time(f"Extraction completed in {extract_time:.2f}s")
                except asyncio.TimeoutError:
                    print(f"[CHART_TOOL] ⏱️ Extraction timeout after 60 seconds")
                    print(f"[CHART_TOOL] 📊 Checking partial results...")
                    print(f"[CHART_TOOL] 💾 Found {len(self.partial_results)} records in storage")
                    
                    # Check if we have partial results
                    if self.partial_results:
                        # Apply limit to partial results
                        partial_records = self.partial_results[:limit] if limit else self.partial_results
                        
                        print(f"[CHART_TOOL] ✅ Returning {len(partial_records)} partial records collected before timeout")
                        
                        # Add completeness metadata
                        completeness_metadata = self._add_completeness_metadata(
                            data=partial_records,
                            requested_count=requested_count or limit,
                            requested_fields=required_fields,
                            task_description=task_description
                        )
                        
                        return ToolResult(
                            success=True,  # Success with partial data
                            data=partial_records,
                            metadata={
                                "url": url,
                                "count": len(partial_records),
                                "required_fields": required_fields,
                                "extracted_fields": list(partial_records[0].keys()) if partial_records else [],
                                "timeout": True,
                                "partial": True,
                                **completeness_metadata
                            }
                        )
                    else:
                        # No partial results - true failure
                        return ToolResult(
                            success=False,
                            error="Extraction timeout after 60 seconds with no data collected. Page may be too complex.",
                            metadata={
                                "url": url,
                                "required_fields": required_fields,
                                "timeout": True
                            }
                        )
                
                # Apply limit if specified
                if limit and isinstance(records, list):
                    records = records[:limit]
                
                if not records:
                    return ToolResult(
                        success=False,
                        error="No data extracted. The page may not contain structured data.",
                        metadata={
                            "url": url,
                            "required_fields": required_fields
                        }
                    )
                
                print(f"[CHART_TOOL] Successfully extracted {len(records)} records")
                
                # Add universal completeness metadata
                completeness_metadata = self._add_completeness_metadata(
                    data=records,
                    requested_count=requested_count or limit,
                    requested_fields=required_fields,
                    task_description=task_description
                )
                
                # Log completeness status
                if not completeness_metadata.get("complete", True):
                    print(f"[CHART_TOOL] ⚠️ INCOMPLETE: {completeness_metadata.get('reason')}")
                    print(f"[CHART_TOOL] Coverage: {completeness_metadata.get('coverage', 0):.0%}")
                else:
                    print(f"[CHART_TOOL] ✓ Complete")
                
                return ToolResult(
                    success=True,
                    data=records,
                    metadata={
                        "url": url,
                        "count": len(records),
                        "required_fields": required_fields,
                        "extracted_fields": list(records[0].keys()) if records else [],
                        **completeness_metadata
                    }
                )
            
            finally:
                # Cleanup browser if we created it
                if should_close:
                    print(f"[CHART_TOOL] Cleaning up browser instance")
                    if browser_instance:
                        await browser_instance.close()
                    if playwright_instance:
                        await playwright_instance.stop()
            
        except Exception as e:
            print(f"[CHART_TOOL] Error: {e}")
            import traceback
            traceback.print_exc()
            
            return ToolResult(
                success=False,
                error=f"Chart extraction failed: {str(e)}",
                metadata={
                    "url": url,
                    "required_fields": required_fields
                }
            )
    
    def _validate_extraction(
        self,
        records: List[Dict[str, Any]],
        required_fields: List[str],
        url: str
    ) -> Dict[str, Any]:
        """
        Validate extraction completeness.
        
        Args:
            records: Extracted records
            required_fields: Required field names
            url: Source URL
            
        Returns:
            Validation results
        """
        if not records or not required_fields:
            return {
                "complete": True,
                "coverage": 1.0,
                "missing_fields": []
            }
        
        try:
            # Use ResultValidator if available
            from src.routing.result_validator import ResultValidator
            
            validator = ResultValidator()
            validation = validator.validate(
                records,
                required_fields,
                {"url": url}
            )
            
            return validation
            
        except Exception as e:
            print(f"[CHART_TOOL] Validation error: {e}")
            
            # Fallback validation
            present = set(records[0].keys())
            required = set(required_fields)
            missing = required - present
            coverage = len(present & required) / len(required) if required else 1.0
            
            return {
                "complete": len(missing) == 0,
                "coverage": coverage,
                "missing_fields": list(missing)
            }
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get tool parameters schema.
        
        Returns:
            Parameter schema
        """
        return {
            "url": {
                "type": "string",
                "description": "URL to extract data from (optional if already navigated)",
                "required": False
            },
            "required_fields": {
                "type": "array",
                "description": "List of field names to extract (e.g., ['name', 'price', 'rating'])",
                "required": False,
                "items": {"type": "string"}
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of records to extract",
                "required": False,
                "default": 10
            }
        }
