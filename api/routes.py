"""
API Routes - PRIORITY 2

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Separated route definitions from main.py for better organization.
All agent-related routes are defined here.

Usage:
    from fastapi import FastAPI
    from api.routes import router
    
    app = FastAPI()
    app.include_router(router)
"""

from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_logic import run_agent_task, cancel_task
from src.models.message import TaskRequest, TaskResponse

# Create router for all agent routes
router = APIRouter(
    prefix="",
    tags=["agent"]
)


@router.get("/")
def read_root():
    """
    Root endpoint.
    
    Returns:
        dict: Status message
    """
    return {"status": "KaryaKarta Python Agent is running."}


@router.get("/health")
def health_check():
    """
    Health check endpoint for Docker and monitoring.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "karyakarta-agent",
        "version": "1.0.0"
    }


@router.post("/execute-task", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """
    Submit an agent task to Google Cloud Tasks.
    
    Receives a task request and submits it to Cloud Tasks for async execution.
    Returns immediately while the task runs in the background.
    
    Args:
        request: TaskRequest with prompt, messageId, and sessionId
        
    Returns:
        TaskResponse: Success response with messageId and sessionId
    """
    print(f"[API] Received task request:")
    print(f"  - Prompt: {request.prompt}")
    print(f"  - Message ID: {request.messageId}")
    print(f"  - Session ID: {request.sessionId}")
    
    try:
        from src.services.cloud_tasks_service import get_cloud_tasks_service
        
        print(f"[API] Submitting to Cloud Tasks...")
        
        # Submit to Cloud Tasks
        tasks_service = get_cloud_tasks_service()
        task_name = tasks_service.submit_agent_task(
            prompt=request.prompt,
            message_id=request.messageId,
            session_id=request.sessionId or "default"
        )
        
        print(f"[API] ✅ Task submitted to Cloud Tasks: {task_name}")
        print(f"[API] Returning response to client...")
        
        # Return structured response
        return TaskResponse(
            status="success",
            messageId=request.messageId,
            sessionId=request.sessionId or "default",
            message="Agent task submitted to Cloud Tasks for processing."
        )
        
    except Exception as e:
        print(f"[API] ❌ Failed to submit task: {e}")
        
        # Fallback to direct threading if Cloud Tasks fails
        print(f"[API] Falling back to direct threading...")
        thread = threading.Thread(
            target=run_agent_task,
            args=(request.prompt, request.messageId, request.sessionId or "default"),
            daemon=True,
            name=f"agent-task-{request.messageId}"
        )
        thread.start()
        
        return TaskResponse(
            status="success",
            messageId=request.messageId,
            sessionId=request.sessionId or "default",
            message="Agent task initiated (fallback mode)."
        )


class CancelRequest(BaseModel):
    """Request model for task cancellation."""
    messageId: str


@router.post("/cancel-task")
async def cancel_agent_task(request: CancelRequest):
    """
    Cancel a running agent task.
    
    Args:
        request: CancelRequest with messageId
        
    Returns:
        Cancellation status response
    """
    print(f"[API] Received cancellation request for message: {request.messageId}")
    
    # Call the cancel_task function from agent_logic
    result = cancel_task(request.messageId)
    
    return result
