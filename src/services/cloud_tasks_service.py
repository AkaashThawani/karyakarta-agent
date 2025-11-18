"""
Cloud Tasks Service - GCP Background Job Management

Handles submitting long-running agent tasks to Google Cloud Tasks.
This is the proper way to handle background jobs in Cloud Run.
"""

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import json
import os
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CloudTasksService:
    """
    Service for managing Cloud Tasks submissions.
    
    Cloud Tasks allows Cloud Run to submit work and return immediately,
    while the task executes asynchronously in a worker endpoint.
    """
    
    def __init__(self):
        """Initialize Cloud Tasks client."""
        try:
            self.client = tasks_v2.CloudTasksClient()
            self.project = os.getenv('GCP_PROJECT_ID') or 'karyakarta-478520'
            self.location = os.getenv('GCP_REGION') or 'us-central1'
            self.queue = os.getenv('CLOUD_TASKS_QUEUE') or 'agent-tasks'
            
            # Build queue path
            self.queue_path = self.client.queue_path(
                self.project,
                self.location,
                self.queue
            )
            
            # Get Cloud Run service URL
            self.service_url = os.getenv(
                'CLOUD_RUN_SERVICE_URL',
                'https://karyakarta-agent-1036363856684.us-central1.run.app'
            )
            
            print(f"[CloudTasks] Initialized")
            print(f"  - Project: {self.project}")
            print(f"  - Location: {self.location}")
            print(f"  - Queue: {self.queue}")
            print(f"  - Service URL: {self.service_url}")
            
        except Exception as e:
            print(f"❌ [CloudTasks] Failed to initialize: {e}")
            logger.error(f"Cloud Tasks initialization failed: {e}")
            raise
    
    def submit_agent_task(
        self,
        prompt: str,
        message_id: str,
        session_id: str,
        delay_seconds: int = 0
    ) -> str:
        """
        Submit an agent task to Cloud Tasks.
        
        Args:
            prompt: User's question/request
            message_id: Unique message identifier
            session_id: Session identifier
            delay_seconds: Optional delay before task execution
            
        Returns:
            Task name/ID
        """
        try:
            # Create task payload
            payload = {
                'prompt': prompt,
                'messageId': message_id,
                'sessionId': session_id
            }
            
            # Create the task
            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': f'{self.service_url}/worker/execute-task',
                    'headers': {
                        'Content-Type': 'application/json',
                    },
                    'body': json.dumps(payload).encode(),
                }
            }
            
            # Add delay if specified
            if delay_seconds > 0:
                d = datetime.utcnow() + timedelta(seconds=delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task['schedule_time'] = timestamp
            
            # Submit to Cloud Tasks
            print(f"[CloudTasks] Submitting task for message: {message_id}")
            response = self.client.create_task(
                request={'parent': self.queue_path, 'task': task}
            )
            
            print(f"[CloudTasks] ✅ Task submitted: {response.name}")
            logger.info(f"Cloud Task created: {response.name}")
            
            return response.name
            
        except Exception as e:
            print(f"[CloudTasks] ❌ Failed to submit task: {e}")
            logger.error(f"Failed to submit Cloud Task: {e}")
            raise


# Global instance
_cloud_tasks_service: Optional[CloudTasksService] = None


def get_cloud_tasks_service() -> CloudTasksService:
    """
    Get or create the global Cloud Tasks service instance.
    
    Returns:
        CloudTasksService instance
    """
    global _cloud_tasks_service
    
    if _cloud_tasks_service is None:
        _cloud_tasks_service = CloudTasksService()
    
    return _cloud_tasks_service
