"""
Unit Tests for ScraperTool

Tests for web scraping tool with Playwright and parameter handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tools.scraper import ScraperTool
from src.tools.base import ToolResult


class TestScraperToolInit:
    """Tests for ScraperTool initialization."""
    
    def test_init_without_settings(self):
        """Test ScraperTool initialization without settings."""
        with patch.dict('os.environ', {'BROWSERLESS_API_KEY': 'test_key'}):
            tool = ScraperTool()
            assert tool.logger is None
            assert "test_key" in tool.browserless_url
            assert tool.timeout == 15000
    
    def test_init_with_settings(self, mock_settings):
        """Test ScraperTool initialization with settings."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.timeout == mock_settings.scraper_timeout
        assert mock_settings.browserless_api_key in tool.browserless_url
    
    def test_init_with_logger(self, mock_logger, mock_settings):
        """Test ScraperTool initialization with logger."""
        tool = ScraperTool(logger=mock_logger, settings=mock_settings)
        assert tool.logger == mock_logger


class TestScraperToolProperties:
    """Tests for ScraperTool properties."""
    
    def test_name_property(self, mock_settings):
        """Test tool name property."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.name == "browse_website"
    
    def test_description_property(self, mock_settings):
        """Test tool description property."""
        tool = ScraperTool(settings=mock_settings)
        assert "url" in tool.description.lower()
        assert "webpage" in tool.description.lower()


class TestScraperToolValidation:
    """Tests for ScraperTool parameter validation."""
    
    def test_validate_with_valid_http_url(self, mock_settings):
        """Test validation with valid HTTP URL."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(url="http://example.com") is True
    
    def test_validate_with_valid_https_url(self, mock_settings):
        """Test validation with valid HTTPS URL."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(url="https://example.com") is True
    
    def test_validate_with_nested_kwargs(self, mock_settings):
        """Test validation with nested kwargs (LangChain format)."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(kwargs={"url": "https://example.com"}) is True
    
    def test_validate_missing_url(self, mock_settings):
        """Test validation without URL parameter."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params() is False
        assert tool.validate_params(other_param="value") is False
    
    def test_validate_invalid_url_format(self, mock_settings):
        """Test validation with invalid URL format."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(url="not-a-url") is False
        assert tool.validate_params(url="ftp://example.com") is False
        assert tool.validate_params(url="example.com") is False  # Missing protocol
    
    def test_validate_empty_url(self, mock_settings):
        """Test validation with empty URL."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(url="") is False
    
    def test_validate_non_string_url(self, mock_settings):
        """Test validation with non-string URL."""
        tool = ScraperTool(settings=mock_settings)
        assert tool.validate_params(url=123) is False
        assert tool.validate_params(url=None) is False


class TestScraperToolExecution:
    """Tests for ScraperTool execution."""
    
    @patch('src.tools.scraper.sync_playwright')
    def test_execute_successful_scrape(self, mock_playwright, mock_settings, mock_logger):
        """Test successful website scraping."""
        # Setup mock playwright
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Test content</body></html>"
        mock_page.goto = Mock()
        
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_browser.close = Mock()
        
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(logger=mock_logger, settings=mock_settings)
        result = tool.execute(url="https://example.com")
        
        assert result.success is True
        assert "Successfully browsed" in result.data
        assert result.metadata["url"] == "https://example.com"
        assert "content_length" in result.metadata
        
        # Verify browser interaction
        mock_page.goto.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_logger.status.assert_called()
    
    @patch('src.tools.scraper.sync_playwright')
    def test_execute_with_nested_kwargs(self, mock_playwright, mock_settings):
        """Test execution with nested kwargs (LangChain format)."""
        # Setup mock
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>Content</html>"
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        result = tool.execute(kwargs={"url": "https://example.com"})
        
        assert result.success is True
    
    def test_execute_invalid_parameters(self, mock_settings):
        """Test execution with invalid parameters."""
        tool = ScraperTool(settings=mock_settings)
        
        result = tool.execute()  # No parameters
        
        assert result.success is False
        assert "Invalid parameters" in result.error
    
    @patch('src.tools.scraper.sync_playwright')
    def test_execute_navigation_failure(self, mock_playwright, mock_settings, mock_logger):
        """Test execution when navigation fails."""
        # Setup mock to raise exception
        mock_page = MagicMock()
        mock_page.goto.side_effect = Exception("Navigation timeout")
        
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(logger=mock_logger, settings=mock_settings)
        result = tool.execute(url="https://example.com")
        
        assert result.success is False
        assert "Error browsing" in result.error
        assert "Navigation timeout" in result.error
        mock_logger.error.assert_called()
    
    @patch('src.tools.scraper.sync_playwright')
    def test_execute_connection_failure(self, mock_playwright, mock_settings):
        """Test execution when browser connection fails."""
        # Setup mock to fail connection
        mock_p = MagicMock()
        mock_p.chromium.connect.side_effect = Exception("Connection refused")
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        result = tool.execute(url="https://example.com")
        
        assert result.success is False
        assert "Connection refused" in result.error


class TestScraperToolLangChainIntegration:
    """Tests for ScraperTool LangChain integration."""
    
    def test_as_langchain_tool(self, mock_settings):
        """Test conversion to LangChain tool."""
        tool = ScraperTool(settings=mock_settings)
        langchain_tool = tool.as_langchain_tool()
        
        assert langchain_tool is not None
        assert hasattr(langchain_tool, 'invoke')  # StructuredTool has invoke method
        assert langchain_tool.name == "browse_website"
    
    @patch('src.tools.scraper.sync_playwright')
    def test_langchain_tool_execution(self, mock_playwright, mock_settings):
        """Test executing the LangChain tool."""
        # Setup mock
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>Content</html>"
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        langchain_tool = tool.as_langchain_tool()
        
        # Execute through the LangChain tool - this calls our execute method
        # The langchain_tool is a StructuredTool, so we call it with invoke
        result = langchain_tool.invoke({"url": "https://example.com"})
        
        # Verify the result
        assert "Successfully browsed" in result


class TestScraperToolEdgeCases:
    """Tests for ScraperTool edge cases."""
    
    @patch('src.tools.scraper.sync_playwright')
    def test_very_long_url(self, mock_playwright, mock_settings):
        """Test with very long URL."""
        # Setup mock
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>Content</html>"
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        long_url = "https://example.com/" + "path/" * 100
        result = tool.execute(url=long_url)
        
        assert result.success is True
    
    @patch('src.tools.scraper.sync_playwright')
    def test_url_with_query_params(self, mock_playwright, mock_settings):
        """Test with URL containing query parameters."""
        # Setup mock
        mock_page = MagicMock()
        mock_page.content.return_value = "<html>Content</html>"
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        url_with_params = "https://example.com/search?q=test&page=1"
        result = tool.execute(url=url_with_params)
        
        assert result.success is True
        assert url_with_params in result.metadata["url"]
    
    @patch('src.tools.scraper.sync_playwright')
    def test_large_page_content(self, mock_playwright, mock_settings):
        """Test with large page content."""
        # Setup mock with large content
        large_content = "<html><body>" + ("x" * 1000000) + "</body></html>"
        mock_page = MagicMock()
        mock_page.content.return_value = large_content
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.connect.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_p
        
        tool = ScraperTool(settings=mock_settings)
        result = tool.execute(url="https://example.com")
        
        assert result.success is True
        assert result.metadata["content_length"] > 1000000
