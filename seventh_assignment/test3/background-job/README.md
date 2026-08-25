# Background Job API (FastAPI + Inngest)

A backend service implementing fast request handling, durable background jobs, error retries, and scheduled cron workflows.

## How to Run It
1. **Start the API server (Terminal 1):**
   ```bash
   uvicorn main:app --reload --port 8000