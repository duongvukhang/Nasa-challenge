import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes_fits import router as fits_router
from app.api.routes_observations import router as obs_router
from app.api.routes_archive import router as archive_router
from app.api.routes_tracking import router as tracking_router
from app.api.routes_prediction import router as prediction_router
from app.api.routes_samples import router as samples_router
from app.services.sample_generator import ensure_demo_dataset

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure baseline demonstration datasets exist on boot."""
    try:
        ensure_demo_dataset()
    except Exception as e:
        print(f"[Warning] Failed to generate demo dataset at startup: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Interactive NASA SPHEREx Infrared Sky Explorer backend API for the 2026 NASA Space Apps Challenge.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(fits_router, prefix=settings.API_V1_PREFIX)
app.include_router(obs_router, prefix=settings.API_V1_PREFIX)
app.include_router(archive_router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking_router, prefix=settings.API_V1_PREFIX)
app.include_router(prediction_router, prefix=settings.API_V1_PREFIX)
app.include_router(samples_router, prefix=settings.API_V1_PREFIX)

@app.get("/api/health")
def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "SkyTrace API",
        "version": settings.VERSION,
        "timestamp": time.time()
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)}
    )
