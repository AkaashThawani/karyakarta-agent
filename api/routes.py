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
from agent_logic import run_agent_task
from src.models.message import TaskRequest, TaskResponse

# Create router for all agent routes
router = APIRouter(
    prefix="",
    tags=["agent"]
)


@router.get("/")
def read_root():
    """
    Health check endpoint.
    
    Returns:
        dict: Status message
    """
    return {"status": "KaryaKarta Python Agent is running."}


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
