import datetime
import logging
import uuid

import inngest
import inngest.fast_api
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Report API")

# In-memory store: forgets everything on restart (same lesson as A1, still not a bug).
reports: dict[str, dict] = {}

# The "worker in a separate room". is_production=False talks to the local Dev Server (no account, no keys).
inngest_client = inngest.Inngest(app_id="report-api", is_production=False, logger=logging.getLogger("uvicorn"))


@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


@inngest_client.create_function(fn_id="make-report", trigger=inngest.TriggerEvent(event="report/requested"))
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]

    # Step 1: the slow work (a stand-in for an AI call or a big export).
    await ctx.step.sleep("do-the-slow-work", datetime.timedelta(seconds=8))

    # Step 2: build the result and save it.
    async def build_report() -> dict:
        result = f"A very thorough report about {topic}: {len(topic)} letters of pure insight."
        reports[report_id].update(status="done", result=result,
                                  finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        return {"id": report_id, "result": result}

    return await ctx.step.run("build-report", build_report)


class ReportRequest(BaseModel):
    topic: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=202)
async def create_report(body: ReportRequest):
    report_id = uuid.uuid4().hex[:8]
    reports[report_id] = {"id": report_id, "topic": body.topic, "status": "pending"}
    await inngest_client.send(inngest.Event(name="report/requested", data={"id": report_id, "topic": body.topic}))
    return {"id": report_id, "status": "pending"}  # 202: "I have the order, work starts soon"


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = reports.get(report_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": f"Report {report_id} not found"})
    return report


# Serves the functions at /api/inngest so the Dev Server can discover and call them.
inngest.fast_api.serve(app, inngest_client, [say_hello, make_report])
