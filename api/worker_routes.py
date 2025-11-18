"""
Worker Routes - Cloud Tasks Handler

Handles background job execution triggered by Cloud Tasks.
This endpoint is called by Cloud Tasks to execute agent tasks.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from agent_logic import run_agent_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/worker", tags=["worker"])


class WorkerTaskRequest(BaseModel):
    """Request model for worker task execution."""
    prompt: str
    messageId: str
    sessionId: str


@router.post("/execute-task")
async def worker_execute_task(request: WorkerTaskRequest):
    """
    Worker endpoint that actually executes the agent task.
    
    This endpoint is called by Cloud Tasks (not directly by users).
    It runs the long-running agent task and returns when complete.
    
    Args:
        request: Task parameters from Cloud Tasks
        
    Returns:
        Execution result
    """
    print(f"\n{'='*60}")
    print(f"[Worker] Task received from Cloud Tasks")
    print(f"  - Message ID: {request.messageId}")
    print(f"  - Session ID: {request.sessionId}")
    print(f"  - Prompt: {request.prompt[:50]}...")
    print(f"{'='*60}\n")
    
    try:
        # Execute the agent task (this can take several minutes)
        result = run_agent_task(
            prompt=request.prompt,
            message_id=request.messageId,
            session_id=request.sessionId
        )
        
        print(f"[Worker] ✅ Task completed for message: {request.messageId}")
        
        return {
            "status": "success",
            "messageId": request.messageId,
            "sessionId": request.sessionId,
            "result": result
        }
        
    except Exception as e:
        print(f"[Worker] ❌ Task failed: {e}")
        logger.error(f"Worker task failed: {e}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Worker task execution failed: {str(e)}"
        )
