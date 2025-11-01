"""
API Call Tool - Lightweight HTTP requests for APIs

Makes HTTP requests (GET/POST) with query parameters.
Much lighter than Playwright for pure API requests.
"""

import requests
from typing import Dict, Any, Optional
from src.tools.base import BaseTool


class APICallTool(BaseTool):
    """
    Makes HTTP API calls with query parameters.
    
    Supports:
    - GET/POST requests
    - Query parameters
    - JSON request/response
    - Custom headers
    
    Much faster and lighter than using Playwright for APIs.
    """
    
    @property
    def name(self) -> str:
        return "api_call"
    
    @property
    def description(self) -> str:
        return "Make HTTP API requests (GET/POST) with query parameters and JSON responses"
    
    def _execute_impl(self, **kwargs) -> Any:
        """
        Execute API call implementation.
        
        Args:
            url: API endpoint URL (required)
            method: HTTP method - GET or POST (default: GET)
            params: Query parameters dict (e.g., {"limit": 10, "sort": "id"})
            headers: Optional headers dict
            body: Optional request body for POST (will be sent as JSON)
            timeout: Request timeout in seconds (default: 10)
        
        Returns:
            ToolResult with success status and data
        """
        from src.tools.base import ToolResult
        
        url = kwargs.get("url")
        if not url:
            return ToolResult(success=False, error="URL is required")
        
        method = kwargs.get("method", "GET").upper()
        params = kwargs.get("params", {})
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        timeout = kwargs.get("timeout", 10)
        
        print(f"[API_CALL] {method} {url}")
        if params:
            print(f"[API_CALL] Query params: {params}")
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, params=params, json=body, headers=headers, timeout=timeout)
            else:
                return ToolResult(success=False, error=f"Unsupported method: {method}")
            
            response.raise_for_status()
            
            # Try to parse JSON
            try:
                data = response.json()
                print(f"[API_CALL] ✓ Success: {len(str(data))} chars JSON")
            except:
                data = response.text
                print(f"[API_CALL] ✓ Success: {len(data)} chars text")
            
            return ToolResult(
                success=True,
                data=data,
                metadata={
                    "status_code": response.status_code,
                    "url": response.url
                }
            )
            
        except requests.exceptions.Timeout:
            return ToolResult(
                success=False,
                error=f"Request timed out after {timeout}s"
            )
        except requests.exceptions.RequestException as e:
            return ToolResult(
                success=False,
                error=f"Request failed: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
