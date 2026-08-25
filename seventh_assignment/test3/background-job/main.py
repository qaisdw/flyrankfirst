import os
import inngest
import inngest.fast_api
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Optional

# Initialize FastAPI
app = FastAPI()

# In-memory storage for reports (Stage 2)
reports_db = {}

# Initialize Inngest Client (Stage 1)
inngest_client = inngest.Inngest(app_id="report-api", is_production=False)

# Pydantic model for incoming report requests
class ReportRequest(BaseModel):
    topic: Optional[str] = None

# STAGE 0: Hello Server Checkpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# STAGE 2 & 3: POST /reports (Accept now, work later + validation)
@app.post("/reports", status_code=202)
async def create_report(body: ReportRequest):
    # Stage 3 Validation: Reject bad input at the door
    if not body.topic or not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")

    import uuid
    report_id = str(uuid.uuid4())

    # Save initial pending state in-memory
    reports_db[report_id] = {
        "id": report_id,
        "topic": body.topic,
        "status": "pending",
        "result": None
    }

    # Send event to Inngest to trigger background job
    await inngest_client.send(
        inngest.Event(
            name="report/requested",
            data={
                "id": report_id,
                "topic": body.topic
            }
        )
    )

    return {
        "id": report_id,
        "status": "pending"
    }

# STAGE 2: GET /reports/:id (Status endpoint)
@app.get("/reports/{report_id}")
def get_report(report_id: str):
    if report_id not in reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    return reports_db[report_id]

# STAGE 1 & 2 & 3: Inngest Functions Setup
@inngest_client.create_function(
    fn_id="say-hello",
    trigger=inngest.TriggerEvent(event="test/hello"),
)
async def say_hello(ctx: inngest.Context, step: inngest.Step) -> str:
    # 5-second sleep step
    await step.sleep("sleep-5s", 5)
    return "Hello from the background!"

@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event="report/requested"),
    retries=2, # Stage 3: Limit retries to 2 for testing backoff
)
async def make_report(ctx: inngest.Context, step: inngest.Step):
    data = ctx.event.data
    report_id = data["id"]
    topic = data["topic"]

    # Stage 3: Simulate oven breaking if topic is "fail"
    @step.run("check-oven")
    def check_oven():
        if topic.lower() == "fail":
            raise Exception("The report oven is broken!")
        return "Oven operational"

    await step.run("check-oven-run", check_oven)

    # Step 1: Simulate 8 seconds of slow work (AI call / big export)
    await step.sleep("do-the-slow-work", "8s")

    # Step 2: Build the result and save it
    @step.run("build-report")
    def build_result():
        result_text = f"Successfully generated deep-dive report for topic: {topic}"
        reports_db[report_id]["status"] = "done"
        reports_db[report_id]["result"] = result_text
        return result_text

    return await step.run("build-report-run", build_result)

# STAGE 4: The Clock Knocks (Cron Job running every minute)
@inngest_client.create_function(
    fn_id="heartbeat",
    trigger=inngest.TriggerCron(cron="* * * * *"),
)
async def heartbeat(ctx: inngest.Context, step: inngest.Step):
    @step.run("log-summary")
    def log_summary():
        pending_count = sum(1 for r in reports_db.values() if r["status"] == "pending")
        done_count = sum(1 for r in reports_db.values() if r["status"] == "done")
        summary = f"HEARTBEAT SUMMARY -> Pending: {pending_count}, Done: {done_count}"
        print(summary)
        return summary

    return await step.run("log-summary-run", log_summary)

# Serve Inngest endpoints to connect with the Dev Server
inngest.fast_api.serve(
    app,
    inngest_client,
    [
        say_hello,
        make_report,
        heartbeat,
    ],
)