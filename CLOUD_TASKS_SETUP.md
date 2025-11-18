# Cloud Tasks Setup Guide

## Overview

Cloud Tasks is Google Cloud's managed service for executing background jobs. This replaces threading/background tasks for reliable async execution in Cloud Run.

## Step 1: Enable Cloud Tasks API

```bash
# Enable Cloud Tasks API
gcloud services enable cloudtasks.googleapis.com

# Verify it's enabled
gcloud services list --enabled | grep cloudtasks
```

## Step 2: Create Task Queue

```bash
# Create the queue
gcloud tasks queues create agent-tasks \
  --location=us-central1 \
  --max-concurrent-dispatches=10 \
  --max-dispatches-per-second=5

# Verify queue was created
gcloud tasks queues describe agent-tasks --location=us-central1
```

## Step 3: Set Environment Variables

Add these to your Cloud Run service:

```bash
# Get your project ID
gcloud config get-value project

# Update Cloud Run with new env vars
gcloud run services update karyakarta-agent \
  --region=us-central1 \
  --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID,GCP_REGION=us-central1,CLOUD_TASKS_QUEUE=agent-tasks"
```

Replace `YOUR_PROJECT_ID` with your actual project ID from the first command.

## Step 4: Grant IAM Permissions

Cloud Tasks needs permission to invoke your Cloud Run service:

```bash
# Get the default Cloud Tasks service account
PROJECT_ID=$(gcloud config get-value project)
TASKS_SA="service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com"

# Grant invoker role
gcloud run services add-iam-policy-binding karyakarta-agent \
  --region=us-central1 \
  --member="serviceAccount:${TASKS_SA}" \
  --role="roles/run.invoker"
```

**Note:** If you don't know your PROJECT_NUMBER, get it with:
```bash
gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)"
```

## Step 5: Deploy Code

```bash
cd karyakarta-agent

# Add all Cloud Tasks files
git add requirements.txt main.py api/routes.py api/worker_routes.py src/services/cloud_tasks_service.py

# Commit
git commit -m "Implement Cloud Tasks for background job execution"

# Push (triggers deployment)
git push origin master
```

## Step 6: Test

After deployment completes (~5-10 minutes):

1. Send a message to your agent
2. Check logs:
   ```bash
   gcloud run services logs read karyakarta-agent --region=us-central1 --limit=100
   ```

You should see:
```
[API] Submitting to Cloud Tasks...
[CloudTasks] ✅ Task submitted
[Worker] Task received from Cloud Tasks
[AgentLogic] ===== TASK STARTED =====
[AgentManager] Processing task
```

## Troubleshooting

### Error: "Queue not found"
```bash
# List all queues
gcloud tasks queues list --location=us-central1

# Create if missing
gcloud tasks queues create agent-tasks --location=us-central1
```

### Error: "Permission denied"
```bash
# Check IAM policy
gcloud run services get-iam-policy karyakarta-agent --region=us-central1

# Grant permissions again if needed
```

### Error: "Cloud Tasks API not enabled"
```bash
gcloud services enable cloudtasks.googleapis.com
```

## Architecture

### Before (Didn't Work):
```
User → API → background_tasks.add_task() → (never executes)
```

### After (Cloud Tasks):
```
User → API → Cloud Tasks → Worker Endpoint → Agent Execution
          ↓
    Returns immediately
```

## Benefits

✅ Reliable background execution in Cloud Run  
✅ Automatic retries on failure  
✅ Rate limiting and concurrency control  
✅ Task monitoring and management  
✅ Scales automatically

## Next Steps

After setup completes:
1. Test agent responds to messages
2. Verify logs show task execution
3. Remove threading fallback code if Cloud Tasks works

## Fallback Mode

The code includes automatic fallback to threading if Cloud Tasks fails:
- Useful during local development
- Provides graceful degradation
- Can be removed once Cloud Tasks is confirmed working
