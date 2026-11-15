"""Web UI + API for the NL filter pipeline. Run with: python server.py"""
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import ConfigError, Settings
from examples import TEST_GROUPS
from logging_config import setup_logging
from pipeline import NLFilterPipeline

log = logging.getLogger(__name__)
INDEX_HTML = Path(__file__).parent / "static" / "index.html"


class QueryIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank")
        return v


def _error(status: str, code: int, type_: str, message: str, details=None) -> JSONResponse:
    error = {"type": type_, "message": message}
    if details:
        error["details"] = details
    return JSONResponse({"status": status, "code": code, "error": error}, status_code=code)


def create_app(pipeline: Optional[NLFilterPipeline] = None, settings: Optional[Settings] = None) -> FastAPI:
    # Fail fast at startup if credentials are not configured. They are never sent to the browser.
    settings = settings or Settings.from_env()
    pipeline = pipeline or NLFilterPipeline(model_name=os.getenv("MODEL_NAME", "llama3.2"))

    setup_logging(secrets=[settings.auth_token])
    app = FastAPI(title="NL Product Filter")
    app.state.settings = settings            # used when the generated request is dispatched to the product API
    app.state.pipeline = pipeline

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        """Request id + one access-log line per request. Never logs bodies or headers."""
        request_id = request.headers.get("X-Request-ID", "")[:64] or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("Unhandled error", extra={"request_id": request_id})
            response = _error("HALTED_INTERNAL_ERROR", 500, "INTERNAL_FAILURE", "An unexpected error occurred.")
        response.headers["X-Request-ID"] = request_id
        ms = round((time.perf_counter() - start) * 1000)
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        log.log(level, "%s %s -> %s (%d ms)", request.method, request.url.path, response.status_code, ms,
                extra={"request_id": request_id, "method": request.method, "path": request.url.path,
                       "status": response.status_code, "duration_ms": ms})
        return response

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]) or "body", "message": e["msg"]}
                   for e in exc.errors()]
        return _error("HALTED_VALIDATION_ERROR", 422, "INVALID_REQUEST", "The request body is invalid.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return _error("HALTED_HTTP_ERROR", exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return _error("HALTED_INTERNAL_ERROR", 500, "INTERNAL_FAILURE", "An unexpected error occurred.")

    @app.get("/")
    def index():
        return FileResponse(INDEX_HTML)

    @app.get("/api/examples")
    def examples():
        return TEST_GROUPS

    # Plain `def` so FastAPI runs the blocking Ollama calls in a worker thread.
    @app.post("/api/translate")
    def translate(body: QueryIn):
        result = pipeline.translate(body.query)
        return JSONResponse(result, status_code=result["code"])   # HTTP status mirrors the body's code

    return app


if __name__ == "__main__":
    try:
        application = create_app()
    except ConfigError as err:                      # clear message instead of a traceback
        raise SystemExit(f"Configuration error: {err}. See README.md.")
    uvicorn.run(application, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8001")),
                access_log=False, log_config=None)   # our middleware does the access logging
