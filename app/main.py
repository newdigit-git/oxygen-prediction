from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import analytics, sessions, telemetry
from app.core.config import get_settings
from app.core.database import SessionLocal

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Real-time telemetry ingestion and analytics backend for smart oxygen systems.",
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

app.include_router(telemetry.router, prefix=settings.API_V1_STR)
app.include_router(sessions.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": settings.PROJECT_NAME, "version": settings.VERSION}


@app.get("/health/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health", include_in_schema=False)
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": settings.PROJECT_NAME}


@app.get("/health/ready", include_in_schema=False)
def readiness() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ready", "database": "reachable"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
