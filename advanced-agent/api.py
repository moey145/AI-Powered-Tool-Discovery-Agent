import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import Settings, get_settings
from src.logger import get_logger, request_id, setup_logging
from src.models import ResearchRequest, ResearchResponse, ResearchResult
from src.net import create_client
from src.rate_limit import RateLimiter
from src.workflow import Workflow, create_workflow

logger = get_logger("api")

VERSION = "2.0.0"
EXAMPLES = [
    "Python web frameworks",
    "JavaScript testing tools",
    "React state management libraries",
    "CI/CD platforms",
    "Machine learning libraries",
    "DevOps automation tools",
]
GENERIC_ERROR = "Something went wrong while researching. Please try again."
TIMEOUT_ERROR = "The research took too long. Please try again."


def client_ip(request: Request) -> str:
    # Trusted proxies append the real client last, and earlier entries can be forged.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    retry_after = request.app.state.limiter.check(client_ip(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many searches. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def _to_response(result: ResearchResult, req_id: str, started: float) -> ResearchResponse:
    return ResearchResponse(
        **result.model_dump(),
        request_id=req_id,
        processing_time=round(time.monotonic() - started, 2),
    )


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


async def _event_stream(workflow: Workflow, query: str, limit: float) -> AsyncIterator[str]:
    req_id = uuid.uuid4().hex[:8]
    request_id.set(req_id)
    started = time.monotonic()
    logger.info("Streaming research for: %s", query)
    try:
        async with asyncio.timeout(limit):
            async for event in workflow.stream(query):
                if event["type"] == "result":
                    response = _to_response(event["result"], req_id, started)
                    yield _sse({"type": "result", "result": response.model_dump(mode="json")})
                else:
                    yield _sse(event)
    except TimeoutError:
        logger.warning("Research timed out")
        yield _sse({"type": "error", "message": TIMEOUT_ERROR, "request_id": req_id})
    except Exception:
        logger.exception("Research failed")
        yield _sse({"type": "error", "message": GENERIC_ERROR, "request_id": req_id})


def create_app(
    settings: Settings | None = None,
    workflow_factory: Callable[[Settings, Any], Workflow] = create_workflow,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with create_client(settings) as client:
            app.state.workflow = workflow_factory(settings, client)
            yield

    app = FastAPI(title="Tool Discovery Agent", version=VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute, settings.daily_search_budget)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "version": VERSION}

    @app.get("/examples")
    async def examples() -> dict[str, list[str]]:
        return {"examples": EXAMPLES}

    @app.post("/research", dependencies=[Depends(enforce_rate_limit)])
    async def research(body: ResearchRequest, request: Request) -> ResearchResponse:
        req_id = uuid.uuid4().hex[:8]
        request_id.set(req_id)
        started = time.monotonic()
        try:
            async with asyncio.timeout(settings.total_timeout):
                result = await request.app.state.workflow.run(body.query)
        except TimeoutError:
            logger.warning("Research timed out")
            raise HTTPException(status_code=504, detail=TIMEOUT_ERROR) from None
        return _to_response(result, req_id, started)

    @app.post("/research/stream", dependencies=[Depends(enforce_rate_limit)])
    async def research_stream(body: ResearchRequest, request: Request) -> StreamingResponse:
        return StreamingResponse(
            _event_stream(request.app.state.workflow, body.query, settings.total_timeout),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": GENERIC_ERROR})

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
