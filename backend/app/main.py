from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routes import applications, companies, cv, features, jobs, logs, match, settings as settings_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    Path("uploads/screenshots").mkdir(parents=True, exist_ok=True)
    Path("uploads/cv").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="AI Job Hunter API",
    version="0.1.0",
    description="Backend for the AI Job Hunter dashboard.",
    lifespan=lifespan,
)

origins = [settings.frontend_origin]
if settings.frontend_origin == "http://localhost:3000":
    origins.append("http://127.0.0.1:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(cv.router, prefix="/cv", tags=["cv"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(match.router, prefix="/match", tags=["match"])
app.include_router(settings_routes.router, prefix="/settings", tags=["settings"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(features.router, prefix="/features", tags=["features"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])


@app.get("/")
async def root():
    from .services.ai_service import get_provider_info
    return {
        "name": "AI Job Hunter API",
        "version": "0.1.0",
        "max_applications_per_day_hard_limit": settings.max_applications_per_day_hard_limit,
        "ai": get_provider_info(),
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    from .services.ai_service import get_provider_info
    return {"status": "ok", "ai": get_provider_info()}
