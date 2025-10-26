"""
Unit Tests for SearchTool

Tests for Google search tool with parameter handling fixes.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tools.search import SearchTool
from src.tools.base import ToolResult


class TestSearchToolInit:
    """Tests for SearchTool initialization."""
    
    def test_init_without_logger(self):
        """Test SearchTool initialization without logger."""
        tool = SearchTool()
        assert tool.logger is None
        assert tool.search is not None
    
    def test_init_with_logger(self, mock_logger):
        """Test SearchTool initialization with logger."""
        tool = SearchTool(logger=mock_logger)
        assert tool.logger == mock_logger


class TestSearchToolProperties:
    """Tests for SearchTool properties."""
    
    def test_name_property(self):
        """Test tool name property."""
        tool = SearchTool()
        assert tool.name == "google_search"
    
    def test_description_property(self):
        """Test tool description property."""
        tool = SearchTool()
        assert "search" in tool.description.lower()
        assert "google" in tool.description.lower()


class TestSearchToolValidation:
    """Tests for SearchTool parameter validation."""
    
    def test_validate_with_query_parameter(self):
        """Test validation with 'query' parameter."""
        tool = SearchTool()
        assert tool.validate_params(query="test search") is True
    
    def test_validate_with_q_parameter(self):
        """Test validation with 'q' parameter (LangChain style)."""
        tool = SearchTool()
        assert tool.validate_params(q="test search") is True
    
    def test_validate_with_nested_kwargs_query(self):
        """Test validation with nested kwargs containing 'query'."""
        tool = SearchTool()
        assert tool.validate_params(kwargs={"query": "test search"}) is True
    
    def test_validate_with_nested_kwargs_q(self):
        """Test validation with nested kwargs containing 'q'."""
        tool = SearchTool()
        assert tool.validate_params(kwargs={"q": "test search"}) is True
    
    def test_validate_missing_query(self):
        """Test validation without query parameter."""
        tool = SearchTool()
        assert tool.validate_params() is False
        assert tool.validate_params(other_param="value") is False
    
    def test_validate_empty_query(self):
        """Test validation with empty query string."""
        tool = SearchTool()
        assert tool.validate_params(query="") is False
        assert tool.validate_params(q="") is False
    
    def test_validate_non_string_query(self):
        """Test validation with non-string query."""
        tool = SearchTool()
        assert tool.validate_params(query=123) is False
        assert tool.validate_params(query=None) is False
        assert tool.validate_params(q=[]) is False


class TestSearchToolExecution:
    """Tests for SearchTool execution."""
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_execute_successful_search(self, mock_wrapper_class):
        """Test successful search execution."""
        # Setup mock
        mock_search = Mock()
        mock_search.run.return_value = "Search results: Python is a programming language"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        # Execute with 'query' parameter
        result = tool.execute(query="Python programming")
        
        assert result.success is True
        assert "Python" in result.data
        assert result.error is None
        assert result.metadata["query"] == "Python programming"
        mock_search.run.assert_called_once_with("Python programming")
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_execute_with_q_parameter(self, mock_wrapper_class):
        """Test execution with 'q' parameter (LangChain style)."""
        mock_search = Mock()
        mock_search.run.return_value = "Search results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        result = tool.execute(q="test query")
        
        assert result.success is True
        mock_search.run.assert_called_once_with("test query")
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_execute_with_nested_kwargs(self, mock_wrapper_class):
        """Test execution with nested kwargs (LangChain format)."""
        mock_search = Mock()
        mock_search.run.return_value = "Search results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        # This is how LangChain passes parameters
        result = tool.execute(kwargs={"q": "nested query"})
        
        assert result.success is True
        mock_search.run.assert_called_once_with("nested query")
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_execute_with_logger(self, mock_wrapper_class, mock_logger):
        """Test execution with logger."""
        mock_search = Mock()
        mock_search.run.return_value = "Search results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool(logger=mock_logger)
        tool.search = mock_search
        
        result = tool.execute(query="test")
        
        assert result.success is True
        # Verify logger was called
        assert mock_logger.status.call_count >= 2  # Start and completion
    
    def test_execute_invalid_parameters(self):
        """Test execution with invalid parameters."""
        tool = SearchTool()
        
        result = tool.execute()  # No parameters
        
        assert result.success is False
        assert "Invalid parameters" in result.error
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_execute_api_failure(self, mock_wrapper_class):
        """Test execution when API fails."""
        mock_search = Mock()
        mock_search.run.side_effect = Exception("API Error")
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        result = tool.execute(query="test")
        
        assert result.success is False
        assert "failed" in result.error.lower()
        assert "API Error" in result.error


class TestSearchToolLangChainIntegration:
    """Tests for SearchTool LangChain integration."""
    
    def test_as_langchain_tool(self):
        """Test conversion to LangChain tool."""
        tool = SearchTool()
        langchain_tool = tool.as_langchain_tool()
        
        assert langchain_tool is not None
        assert hasattr(langchain_tool, 'invoke')  # StructuredTool has invoke method
        assert langchain_tool.name == "google_search"
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_langchain_tool_execution(self, mock_wrapper_class):
        """Test executing the LangChain tool."""
        # Setup mock to return search results
        mock_search = Mock()
        mock_search.run.return_value = "Search results"
        mock_wrapper_class.return_value = mock_search
        
        # Create tool (this will use the mocked wrapper)
        tool = SearchTool()
        
        # Convert to LangChain tool
        langchain_tool = tool.as_langchain_tool()
        
        # Execute through the LangChain tool
        result = langchain_tool.invoke({"query": "test"})
        
        # Verify the result contains our mocked search results
        assert "Search results" in result
        # Verify the search was actually called
        mock_search.run.assert_called_once_with("test")


class TestSearchToolEdgeCases:
    """Tests for SearchTool edge cases."""
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_very_long_query(self, mock_wrapper_class):
        """Test with very long query string."""
        mock_search = Mock()
        mock_search.run.return_value = "Results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        long_query = "test " * 1000
        result = tool.execute(query=long_query)
        
        assert result.success is True
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_special_characters_in_query(self, mock_wrapper_class):
        """Test with special characters in query."""
        mock_search = Mock()
        mock_search.run.return_value = "Results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        special_query = "test @#$%^&*()_+ query"
        result = tool.execute(query=special_query)
        
        assert result.success is True
        mock_search.run.assert_called_once_with(special_query)
    
    @patch('src.tools.search.GoogleSerperAPIWrapper')
    def test_unicode_query(self, mock_wrapper_class):
        """Test with unicode characters in query."""
        mock_search = Mock()
        mock_search.run.return_value = "Results"
        mock_wrapper_class.return_value = mock_search
        
        tool = SearchTool()
        tool.search = mock_search
        
        unicode_query = "Python 编程 プログラミング"
        result = tool.execute(query=unicode_query)
        
        assert result.success is True
