"""
Advanced Form and Navigation Tools

Tools for complex browsing scenarios:
- browse_with_form: Fill and submit forms
- browse_with_auth: Handle authentication
- browse_multi_page: Navigate pagination
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
import asyncio
import os


class BrowseWithFormInput(BaseModel):
    """Input schema for browse_with_form tool."""
    url: str = Field(description="URL containing the form")
    form_data: Dict[str, str] = Field(
        description="Form fields to fill {field_name: value}"
    )
    submit_selector: Optional[str] = Field(
        default="button[type='submit']",
        description="CSS selector for submit button"
    )
    wait_after: Optional[int] = Field(
        default=3,
        description="Seconds to wait after submission"
    )


class BrowseWithAuthInput(BaseModel):
    """Input schema for browse_with_auth tool."""
    url: str = Field(description="URL requiring authentication")
    username: str = Field(description="Username or email")
    password: str = Field(description="Password")
    username_selector: Optional[str] = Field(
        default="input[type='email'], input[name='username']",
        description="CSS selector for username field"
    )
    password_selector: Optional[str] = Field(
        default="input[type='password']",
        description="CSS selector for password field"
    )
    submit_selector: Optional[str] = Field(
        default="button[type='submit']",
        description="CSS selector for login button"
    )


class BrowseMultiPageInput(BaseModel):
    """Input schema for browse_multi_page tool."""
    start_url: str = Field(description="Starting URL")
    max_pages: Optional[int] = Field(
        default=5,
        description="Maximum pages to navigate"
    )
    next_selector: Optional[str] = Field(
        default="a[rel='next'], .next, .pagination a:last-child",
        description="CSS selector for 'Next' link"
    )
    wait_between: Optional[int] = Field(
        default=2,
        description="Seconds to wait between pages"
    )


class BrowseWithFormTool(BaseTool):
    """Tool for filling and submitting forms."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_with_form"
    
    @property
    def description(self) -> str:
        return """Fill and submit web forms.
        
        Use for search forms, contact forms, etc.
        
        Parameters:
        - url: Page with form
        - form_data: Fields to fill {name: value}
        - submit_selector: Submit button selector
        - wait_after: Wait time after submission
        
        Returns: Page content after form submission
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        url = kwargs.get("url", "")
        form_data = kwargs.get("form_data", {})
        return bool(url and form_data)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        form_data = kwargs.get("form_data", {})
        submit_selector = kwargs.get("submit_selector", "button[type='submit']")
        wait_after = kwargs.get("wait_after", 3)
        
        if not url or not form_data:
            return ToolResult(
                success=False,
                error="URL and form_data are required",
                metadata={}
            )
        
        try:
            content = asyncio.run(
                self._browse_with_form(url, form_data, submit_selector, wait_after)
            )
            
            return ToolResult(
                success=True,
                data=content,
                metadata={"url": url, "fields_filled": len(form_data)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"url": url})
    
    async def _browse_with_form(
        self, url: str, form_data: Dict[str, str], submit_selector: str, wait_after: int
    ) -> str:
        """Fill and submit form."""
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
                
                # Fill form fields
                for field_name, value in form_data.items():
                    # Try different selector strategies
                    selectors = [
                        f"input[name='{field_name}']",
                        f"#{field_name}",
                        f"textarea[name='{field_name}']",
                        f"select[name='{field_name}']"
                    ]
                    
                    filled = False
                    for selector in selectors:
                        try:
                            await page.fill(selector, value)
                            filled = True
                            break
                        except:
                            continue
                    
                    if not filled:
                        print(f"[FORM] Warning: Could not fill field '{field_name}'")
                
                # Submit form
                await page.click(submit_selector)
                await page.wait_for_timeout(wait_after * 1000)
                
                content = await page.content()
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=BrowseWithFormInput)
        def browse_with_form(url: str, form_data: Dict[str, str], submit_selector: str = "button[type='submit']", wait_after: int = 3) -> str:
            """Fill and submit web forms."""
            result = tool_instance.execute(url=url, form_data=form_data, submit_selector=submit_selector, wait_after=wait_after)
            return tool_instance.format_result(result)
        
        return browse_with_form


class BrowseWithAuthTool(BaseTool):
    """Tool for browsing pages that require authentication."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_with_auth"
    
    @property
    def description(self) -> str:
        return """Browse pages requiring login/authentication.
        
        Parameters:
        - url: Target URL
        - username: Login username/email
        - password: Login password
        - username_selector: Username field selector
        - password_selector: Password field selector
        - submit_selector: Login button selector
        
        Returns: Page content after authentication
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        url = kwargs.get("url", "")
        username = kwargs.get("username", "")
        password = kwargs.get("password", "")
        return bool(url and username and password)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        url = kwargs.get("url")
        username = kwargs.get("username")
        password = kwargs.get("password")
        username_selector = kwargs.get("username_selector", "input[type='email'], input[name='username']")
        password_selector = kwargs.get("password_selector", "input[type='password']")
        submit_selector = kwargs.get("submit_selector", "button[type='submit']")
        
        # Type validation
        if not url or not isinstance(url, str):
            return ToolResult(success=False, error="URL is required and must be a string", metadata={})
        if not username or not isinstance(username, str):
            return ToolResult(success=False, error="Username is required and must be a string", metadata={})
        if not password or not isinstance(password, str):
            return ToolResult(success=False, error="Password is required and must be a string", metadata={})
        
        try:
            content = asyncio.run(
                self._browse_with_auth(url, username, password, username_selector, password_selector, submit_selector)
            )
            
            return ToolResult(
                success=True,
                data=content,
                metadata={"url": url, "authenticated": True}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"url": url})
    
    async def _browse_with_auth(
        self, url: str, username: str, password: str, 
        username_selector: str, password_selector: str, submit_selector: str
    ) -> str:
        """Browse with authentication."""
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
                
                # Fill login form
                await page.fill(username_selector, username)
                await page.fill(password_selector, password)
                await page.click(submit_selector)
                
                # Wait for navigation after login
                await page.wait_for_timeout(3000)
                
                content = await page.content()
                await browser.close()
                return content
                
            except Exception as e:
                await browser.close()
                raise e
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=BrowseWithAuthInput)
        def browse_with_auth(
            url: str, username: str, password: str,
            username_selector: str = "input[type='email']",
            password_selector: str = "input[type='password']",
            submit_selector: str = "button[type='submit']"
        ) -> str:
            """Browse pages requiring authentication."""
            result = tool_instance.execute(
                url=url, username=username, password=password,
                username_selector=username_selector,
                password_selector=password_selector,
                submit_selector=submit_selector
            )
            return tool_instance.format_result(result)
        
        return browse_with_auth


class BrowseMultiPageTool(BaseTool):
    """Tool for navigating through multiple pages (pagination)."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.browserless_token = os.getenv("BROWSERLESS_API_KEY", "")
    
    @property
    def name(self) -> str:
        return "browse_multi_page"
    
    @property
    def description(self) -> str:
        return """Navigate through paginated content.
        
        Parameters:
        - start_url: Starting page URL
        - max_pages: Maximum pages to navigate
        - next_selector: Selector for 'Next' link
        - wait_between: Wait time between pages
        
        Returns: Combined content from all pages
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("start_url"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        start_url = kwargs.get("start_url")
        max_pages = kwargs.get("max_pages", 5)
        next_selector = kwargs.get("next_selector", "a[rel='next'], .next")
        wait_between = kwargs.get("wait_between", 2)
        
        if not start_url:
            return ToolResult(success=False, error="start_url is required", metadata={})
        
        try:
            content = asyncio.run(
                self._browse_multi_page(start_url, max_pages, next_selector, wait_between)
            )
            
            return ToolResult(
                success=True,
                data=content,
                metadata={"start_url": start_url, "pages_visited": content.count("<!-- PAGE BREAK -->")}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={"start_url": start_url})
    
    async def _browse_multi_page(
        self, start_url: str, max_pages: int, next_selector: str, wait_between: int
    ) -> str:
        """Navigate multiple pages."""
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
                all_content = []
                
                current_url = start_url
                for page_num in range(max_pages):
                    await page.goto(current_url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(wait_between * 1000)
                    
                    content = await page.content()
                    all_content.append(f"<!-- PAGE {page_num + 1} -->\n{content}\n<!-- PAGE BREAK -->")
                    
                    # Try to find next page link
                    try:
                        next_link = await page.query_selector(next_selector)
                        if not next_link:
                            break
                        
                        next_url = await next_link.get_attribute("href")
                        if not next_url:
                            break
                        
                        # Resolve relative URL
                        if not next_url.startswith("http"):
                            from urllib.parse import urljoin
                            next_url = urljoin(current_url, next_url)
                        
                        current_url = next_url
                    except:
                        break
                
                await browser.close()
                return "\n".join(all_content)
                
            except Exception as e:
                await browser.close()
                raise e
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=BrowseMultiPageInput)
        def browse_multi_page(
            start_url: str, max_pages: int = 5,
            next_selector: str = "a[rel='next']",
            wait_between: int = 2
        ) -> str:
            """Navigate through paginated content."""
            result = tool_instance.execute(
                start_url=start_url, max_pages=max_pages,
                next_selector=next_selector, wait_between=wait_between
            )
            return tool_instance.format_result(result)
        
        return browse_multi_page
