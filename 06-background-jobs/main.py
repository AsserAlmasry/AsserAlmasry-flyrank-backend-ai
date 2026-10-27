import datetime
import logging

import inngest
import inngest.fast_api
from fastapi import FastAPI

app = FastAPI(title="Report API")

# The "worker in a separate room". is_production=False talks to the local Dev Server (no account, no keys).
inngest_client = inngest.Inngest(app_id="report-api", is_production=False, logger=logging.getLogger("uvicorn"))


@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


@app.get("/health")
def health():
    return {"status": "ok"}


# Serves the functions at /api/inngest so the Dev Server can discover and call them.
inngest.fast_api.serve(app, inngest_client, [say_hello])
