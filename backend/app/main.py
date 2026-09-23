"""TAKELEY FastAPI application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.legal import router as legal_router
from app.api.share_landing import router as share_landing_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import init_db
from app.services.issue_image_service import issue_image_dir

configure_logging()
settings = get_settings()

app = FastAPI(
    title="TAKELEY API",
    version="0.1.0",
    description="TAKELEY — Issues, takes, and shared intelligence",
)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.environment == "local":
    # Vite (admin) may pick 5174, 5175, ... when ports are busy.
    _cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"
else:
    _cors_kwargs["allow_origins"] = _origins

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    # Ensure upload dir exists before StaticFiles mount is hit.
    issue_image_dir()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "takeley", "env": settings.environment}


app.include_router(legal_router)
app.include_router(share_landing_router)
app.include_router(api_router, prefix="/api/v1")

_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

_image_root = Path(settings.issue_image_dir)
if not _image_root.is_absolute():
    _image_root = Path.cwd() / _image_root
_image_root.mkdir(parents=True, exist_ok=True)
app.mount(
    "/media/issue-images",
    StaticFiles(directory=str(_image_root)),
    name="issue-images",
)
