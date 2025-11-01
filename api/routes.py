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

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
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
async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """
    Execute an agent task in the background.
    
    Receives a task request with prompt, messageId, and sessionId,
    immediately responds with acceptance, and runs the agent logic in the background.
    
    Args:
        request: TaskRequest with prompt, messageId, and sessionId
        background_tasks: FastAPI background tasks manager
        
    Returns:
        TaskResponse: Success response with messageId and sessionId
    """
    print(f"[API] Received task request:")
    print(f"  - Prompt: {request.prompt}")
    print(f"  - Message ID: {request.messageId}")
    print(f"  - Session ID: {request.sessionId}")
    
    # Add the long-running agent task to the background
    background_tasks.add_task(
        run_agent_task, 
        request.prompt, 
        request.messageId,
        request.sessionId or "default"
    )
    
    # Return structured response using Pydantic model
    return TaskResponse(
        status="success",
        messageId=request.messageId,
        sessionId=request.sessionId or "default",
        message="Agent task has been initiated in the background."
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
