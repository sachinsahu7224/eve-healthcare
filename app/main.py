import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.routes import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.utils.exceptions import AppException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("eve_healthcare")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown routines."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("EVE Healthcare Backend Service started successfully.")
    yield
    logger.info("Shutting down EVE Healthcare Backend Service...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade RESTful API service for diagnostic test appointments and idempotent simulated payments.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions with consistent error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format Pydantic request validation errors into a clean, actionable message."""
    errors = exc.errors()
    # Build clean human-readable summary while avoiding raw internal trace dumps
    first_error = errors[0] if errors else {}
    location = " -> ".join(str(loc) for loc in first_error.get("loc", []))
    msg = first_error.get("msg", "Validation error")
    summary = f"Invalid input at '{location}': {msg}" if location else msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": summary,
            "errors": [
                {
                    "loc": err.get("loc"),
                    "msg": err.get("msg"),
                    "type": err.get("type"),
                }
                for err in errors
            ],
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database constraint violations without leaking internal schema or raw queries."""
    logger.warning(f"Database integrity violation: {exc.orig!s}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "A database constraint violation occurred (e.g., duplicate unique record or invalid reference)."
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Catch-all for database errors preventing sensitive credentials or SQL exposure."""
    logger.error(f"Internal database error: {exc!s}", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal database error occurred. Please try again later."},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global catch-all exception handler to prevent unhandled stack trace leaks."""
    logger.error(f"Unhandled exception: {exc!s}", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred."},
    )


# Health Check
@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Health status endpoint for container orchestration and uptime monitoring."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


# Include Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
