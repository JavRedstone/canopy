from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.repository import get_repository
from app.routers import courses, playground, sources
from app.schemas import HealthResponse
from app.settings import get_settings

settings = get_settings()

app = FastAPI(title="Adaptive Source Learning API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment, repository=get_repository().name)


app.include_router(sources.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(playground.router, prefix="/api/v1")
