"""HealthMate AI - FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, CORS_ORIGINS, SEED_DEMO
from .db import init_db
from .routers import appointments, auth, chat, dashboard, medicines, prescriptions, records, report, symptoms, wellness
from .seed import seed_demo


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if SEED_DEMO:
        seed_demo()
    yield


app = FastAPI(title="HealthMate AI API", version="1.0.0", lifespan=lifespan,
              description="Educational health assistant. Not a medical diagnosis or treatment system.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline hardening for a publicly hosted app; API responses (personal health data) are never cached."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline hardening for a publicly hosted app; API responses (personal health data) are never cached."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


for r in (auth, chat, symptoms, medicines, prescriptions, records, wellness, appointments, dashboard, report):
    app.include_router(r.router)

# Serve the built React app (frontend/dist) so one command runs everything.
DIST = Path(BASE_DIR).parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
