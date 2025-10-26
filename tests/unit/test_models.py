"""
Unit Tests for Data Models

Tests for Pydantic models: TaskRequest, TaskResponse, AgentMessage, ToolResult
"""

import pytest
from pydantic import ValidationError
from src.models.message import TaskRequest, TaskResponse, AgentMessage
from src.tools.base import ToolResult


class TestTaskRequest:
    """Tests for TaskRequest model."""
    
    def test_valid_task_request(self):
        """Test creating a valid TaskRequest."""
        request = TaskRequest(
            prompt="Test query",
            messageId="msg_123",
            sessionId="session_456"
        )
        assert request.prompt == "Test query"
        assert request.messageId == "msg_123"
        assert request.sessionId == "session_456"
    
    def test_task_request_default_session_id(self):
        """Test TaskRequest with default sessionId."""
        request = TaskRequest(
            prompt="Test query",
            messageId="msg_123"
        )
        assert request.sessionId == "default"
    
    def test_task_request_missing_prompt(self):
        """Test TaskRequest without required prompt field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(messageId="msg_123")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("prompt",) for error in errors)
    
    def test_task_request_missing_message_id(self):
        """Test TaskRequest without required messageId field."""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(prompt="Test query")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("messageId",) for error in errors)
    
    def test_task_request_empty_prompt(self):
        """Test TaskRequest with empty prompt."""
        # Pydantic allows empty strings, just validates type
        request = TaskRequest(
            prompt="",
            messageId="msg_123"
        )
        assert request.prompt == ""


class TestTaskResponse:
    """Tests for TaskResponse model."""
    
    def test_valid_success_response(self):
        """Test creating a successful TaskResponse."""
        response = TaskResponse(
            status="success",
            messageId="msg_123",
            sessionId="session_456",
            message="Task completed"
        )
        assert response.status == "success"
        assert response.messageId == "msg_123"
        assert response.sessionId == "session_456"
        assert response.message == "Task completed"
        assert response.error is None
    
    def test_valid_error_response(self):
        """Test creating an error TaskResponse."""
        response = TaskResponse(
            status="error",
            messageId="msg_123",
            sessionId="session_456",
            error="Something went wrong",
            message="Task failed"
        )
        assert response.status == "error"
        assert response.error == "Something went wrong"
    
    def test_response_invalid_status(self):
        """Test TaskResponse with invalid status literal."""
        with pytest.raises(ValidationError):
            TaskResponse(
                status="invalid_status",
                messageId="msg_123",
                sessionId="session_456"
            )
    
    def test_response_default_message(self):
        """Test TaskResponse with default message."""
        response = TaskResponse(
            status="success",
            messageId="msg_123",
            sessionId="session_456"
        )
        assert "background" in response.message.lower()


class TestAgentMessage:
    """Tests for AgentMessage model."""
    
    def test_valid_status_message(self):
        """Test creating a status message."""
        msg = AgentMessage(
            type="status",
            message="Processing...",
            timestamp="2025-10-25T12:00:00.000Z"
        )
        assert msg.type == "status"
        assert msg.message == "Processing..."
        assert msg.timestamp == "2025-10-25T12:00:00.000Z"
        assert msg.messageId is None
    
    def test_valid_response_message(self):
        """Test creating a response message."""
        msg = AgentMessage(
            type="response",
            message="Here is the answer",
            timestamp="2025-10-25T12:00:00.000Z",
            messageId="msg_123"
        )
        assert msg.type == "response"
        assert msg.messageId == "msg_123"
    
    def test_valid_error_message(self):
        """Test creating an error message."""
        msg = AgentMessage(
            type="error",
            message="An error occurred",
            timestamp="2025-10-25T12:00:00.000Z"
        )
        assert msg.type == "error"
    
    def test_valid_thinking_message(self):
        """Test creating a thinking message."""
        msg = AgentMessage(
            type="thinking",
            message="Let me think about this...",
            timestamp="2025-10-25T12:00:00.000Z"
        )
        assert msg.type == "thinking"
    
    def test_message_invalid_type(self):
        """Test AgentMessage with invalid type literal."""
        with pytest.raises(ValidationError):
            AgentMessage(
                type="invalid_type",
                message="Test",
                timestamp="2025-10-25T12:00:00.000Z"
            )
    
    def test_message_missing_required_fields(self):
        """Test AgentMessage without required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMessage(type="status")
        
        errors = exc_info.value.errors()
        # Should be missing 'message' and 'timestamp'
        assert len(errors) >= 2


class TestToolResult:
    """Tests for ToolResult model."""
    
    def test_successful_result(self):
        """Test creating a successful ToolResult."""
        result = ToolResult(
            success=True,
            data="Operation completed",
            metadata={"duration": 1.5}
        )
        assert result.success is True
        assert result.data == "Operation completed"
        assert result.error is None
        assert result.metadata == {"duration": 1.5}
    
    def test_failed_result(self):
        """Test creating a failed ToolResult."""
        result = ToolResult(
            success=False,
            error="Operation failed",
            metadata={"attempted": True}
        )
        assert result.success is False
        assert result.error == "Operation failed"
        assert result.data is None
    
    def test_result_with_complex_data(self):
        """Test ToolResult with complex data structure."""
        complex_data = {
            "results": ["item1", "item2"],
            "count": 2,
            "nested": {"key": "value"}
        }
        result = ToolResult(
            success=True,
            data=complex_data
        )
        assert result.data == complex_data
        assert result.metadata == {}
    
    def test_result_default_metadata(self):
        """Test ToolResult with default empty metadata."""
        result = ToolResult(success=True, data="test")
        assert result.metadata == {}
    
    def test_result_missing_success_field(self):
        """Test ToolResult without required success field."""
        with pytest.raises(ValidationError) as exc_info:
            ToolResult(data="test")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("success",) for error in errors)


class TestModelSerialization:
    """Tests for model serialization/deserialization."""
    
    def test_task_request_dict_conversion(self):
        """Test TaskRequest to dict conversion."""
        request = TaskRequest(
            prompt="Test",
            messageId="msg_123",
            sessionId="session_456"
        )
        data = request.model_dump()
        assert data["prompt"] == "Test"
        assert data["messageId"] == "msg_123"
        assert data["sessionId"] == "session_456"
    
    def test_task_request_json_serialization(self):
        """Test TaskRequest JSON serialization."""
        request = TaskRequest(
            prompt="Test",
            messageId="msg_123",
            sessionId="session_456"
        )
        json_str = request.model_dump_json()
        assert "Test" in json_str
        assert "msg_123" in json_str
    
    def test_agent_message_dict_conversion(self):
        """Test AgentMessage to dict conversion."""
        msg = AgentMessage(
            type="status",
            message="Test message",
            timestamp="2025-10-25T12:00:00.000Z",
            messageId="msg_123"
        )
        data = msg.model_dump()
        assert data["type"] == "status"
        assert data["message"] == "Test message"
        assert data["messageId"] == "msg_123"
