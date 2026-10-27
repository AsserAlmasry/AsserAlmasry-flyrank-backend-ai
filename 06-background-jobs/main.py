"""Report API — accept fast, work in the background, report status (BE-06, FastAPI + Inngest)."""
import asyncio
import datetime
import logging
import uuid

import inngest
import inngest.fast_api
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

log = logging.getLogger("uvicorn.error")
app = FastAPI(title="Report API", description="POST /reports answers 202 instantly; an Inngest job does the slow work.")

# In-memory store: forgets everything on restart (same lesson as A1, still not a bug).
reports: dict[str, dict] = {}

# The "worker in a separate room". is_production=False talks to the local Dev Server (no account, no keys).
inngest_client = inngest.Inngest(app_id="report-api", is_production=False, logger=log)


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ Stage 1: hello

@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


# ------------------------------------------------------------------ Stage 2 + 3: the report job

async def mark_failed(ctx: inngest.Context) -> None:
    """Runs once all retries are used up, so the status endpoint can say "failed" instead of "pending" forever."""
    original = ctx.event.data.get("event", {}).get("data", {})
    report = reports.get(original.get("id", ""))
    if report is not None:
        report.update(status="failed", error=str(ctx.event.data.get("error", {}).get("message", "unknown error")),
                      finished_at=now())


@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event="report/requested"),
    retries=2,  # 1 attempt + 2 retries = 3 attempts, then Failed
    on_failure=mark_failed,
    concurrency=[inngest.Concurrency(limit=2)],  # stretch: at most 2 reports are built at the same time
)
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]

    # Stretch — idempotency: if this report was already built (duplicate event, replay), do nothing.
    if reports.get(report_id, {}).get("status") == "done":
        return {"id": report_id, "skipped": "already done"}

    # Step 1: the slow work (a stand-in for an AI call or a big export).
    await ctx.step.sleep("do-the-slow-work", datetime.timedelta(seconds=8))

    # Step 2: build the result and save it.
    async def build_report() -> dict:
        if topic == "fail":
            raise RuntimeError("The report oven is broken!")
        if reports.get(report_id, {}).get("status") == "done":  # double-check right before the write
            return {"id": report_id, "skipped": "already done"}
        # Rendering takes a few seconds of real work. (Inngest does NOT count a sleeping step towards the
        # concurrency limit, only steps that are executing, so this is where the limit of 2 becomes visible.)
        await asyncio.sleep(3)
        result = f"A very thorough report about {topic}: {len(topic)} letters of pure insight."
        reports.setdefault(report_id, {"id": report_id, "topic": topic})
        reports[report_id].update(status="done", result=result, finished_at=now(),
                                  builds=reports[report_id].get("builds", 0) + 1)
        return {"id": report_id, "result": result}

    return await ctx.step.run("build-report", build_report)


# ------------------------------------------------------------------ Stage 4: the clock knocks

@inngest_client.create_function(fn_id="heartbeat", trigger=inngest.TriggerCron(cron="* * * * *"))
async def heartbeat(ctx: inngest.Context) -> dict:
    counts = {s: sum(1 for r in reports.values() if r["status"] == s) for s in ("pending", "done", "failed")}
    ctx.logger.info(f"heartbeat {now()} reports: pending={counts['pending']} done={counts['done']} "
                    f"failed={counts['failed']}")
    return counts


# ------------------------------------------------------------------ HTTP endpoints

class ReportRequest(BaseModel):
    topic: str | None = None


@app.exception_handler(RequestValidationError)
async def bad_body(_: Request, __: RequestValidationError):
    return JSONResponse(status_code=400, content={"error": "Body must be JSON like {\"topic\": \"cats\"}"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=202)
async def create_report(body: ReportRequest):
    # Wrong input is rejected at the door: no job, no retries. Only a wrong *moment* deserves a retry.
    if not body.topic or not body.topic.strip():
        return JSONResponse(status_code=400, content={"error": "topic is required"})
    report_id = uuid.uuid4().hex[:8]
    reports[report_id] = {"id": report_id, "topic": body.topic.strip(), "status": "pending", "created_at": now()}
    await inngest_client.send(inngest.Event(name="report/requested", data={"id": report_id, "topic": body.topic.strip()}))
    return {"id": report_id, "status": "pending"}  # 202: "I have the order, work starts soon"


@app.get("/reports")
def list_reports():
    """Extra: the control panel."""
    return list(reports.values())


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = reports.get(report_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": f"Report {report_id} not found"})
    return report


# Serves the functions at /api/inngest so the Dev Server can discover and call them.
inngest.fast_api.serve(app, inngest_client, [say_hello, make_report, heartbeat])
