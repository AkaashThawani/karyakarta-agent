"""
Pytest Configuration and Fixtures

Provides common fixtures for all tests including mocked services,
configurations, and sample data.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Optional
import os

# Set test environment variables before importing app modules
os.environ["GEMINI_API_KEY"] = "test_google_key"
os.environ["SERPER_API_KEY"] = "test_serper_key"
os.environ["BROWSERLESS_API_KEY"] = "test_browserless_key"
os.environ["LOGGING_URL"] = "http://localhost:3000/api/socket/log"

from src.core.config import Settings
from src.services.logging_service import LoggingService
from src.models.message import TaskRequest, TaskResponse, AgentMessage
from src.tools.base import ToolResult


@pytest.fixture
def mock_settings():
    """Provide test configuration settings."""
    return Settings(
        GEMINI_API_KEY="test_google_key",
        serper_api_key="test_serper_key",
        browserless_api_key="test_browserless_key",
        logging_url="http://localhost:3000/api/socket/log",
        llm_model="gemini-2.5-flash-lite",
        llm_temperature=0.0,
        scraper_timeout=15000,
        api_host="0.0.0.0",
        api_port=8000,
    )


@pytest.fixture
def mock_logger():
    """Provide mock logging service."""
    logger = Mock(spec=LoggingService)
    logger.status = Mock()
    logger.error = Mock()
    logger.log_message = Mock()
    return logger


@pytest.fixture
def sample_task_request():
    """Provide sample task request."""
    return TaskRequest(
        prompt="What is the capital of France?",
        messageId="msg_test_123",
        sessionId="test_session_123",
    )


@pytest.fixture
def sample_task_request_complex():
    """Provide complex task request."""
    return TaskRequest(
        prompt="Find the latest news about AI and summarize it",
        messageId="msg_test_456",
        sessionId="test_session_456",
    )


@pytest.fixture
def sample_agent_message_status():
    """Provide sample status message."""
    return AgentMessage(
        type="status",
        message="Processing your request...",
        timestamp="2025-10-25T12:00:00.000Z",
        messageId="msg_test_123"
    )


@pytest.fixture
def sample_agent_message_response():
    """Provide sample response message."""
    return AgentMessage(
        type="response",
        message="Python is a programming language.",
        timestamp="2025-10-25T12:00:01.000Z",
        messageId="msg_test_123"
    )


@pytest.fixture
def sample_agent_message_error():
    """Provide sample error message."""
    return AgentMessage(
        type="error",
        message="An error occurred while processing.",
        timestamp="2025-10-25T12:00:02.000Z",
        messageId="msg_test_123"
    )


@pytest.fixture
def sample_tool_result_success():
    """Provide successful tool result."""
    return ToolResult(
        success=True,
        data="Search results for Python",
        metadata={"query": "Python programming"}
    )


@pytest.fixture
def sample_tool_result_failure():
    """Provide failed tool result."""
    return ToolResult(
        success=False,
        error="API request failed",
        metadata={"query": "invalid query"}
    )


@pytest.fixture
def mock_serper_api_response():
    """Mock Serper API response."""
    return {
        "searchParameters": {
            "q": "Python programming",
            "type": "search"
        },
        "organic": [
            {
                "title": "Python.org",
                "link": "https://www.python.org/",
                "snippet": "The official home of the Python Programming Language."
            },
            {
                "title": "Python Tutorial",
                "link": "https://www.python.org/tutorial/",
                "snippet": "Learn Python with official tutorials."
            }
        ]
    }


@pytest.fixture
def mock_playwright_page():
    """Mock Playwright page object."""
    page = MagicMock()
    page.goto = Mock()
    page.content = Mock(return_value="<html><body>Test content</body></html>")
    return page


@pytest.fixture
def mock_playwright_browser():
    """Mock Playwright browser object."""
    browser = MagicMock()
    page = MagicMock()
    page.goto = Mock()
    page.content = Mock(return_value="<html><body>Test content</body></html>")
    browser.new_page = Mock(return_value=page)
    browser.close = Mock()
    return browser


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment after each test."""
    yield
    # Cleanup if needed
    pass


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
