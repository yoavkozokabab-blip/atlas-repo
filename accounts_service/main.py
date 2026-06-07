"""Atlas Accounts Service — FastAPI application entry point."""
from __future__ import annotations

import sys, os

# Prepend vendored dependencies
_lib = os.path.join(os.path.dirname(__file__), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, SERVICE_HOST, SERVICE_PORT
from .database import init_db
from .routers import admin, analytics, auth, users

app = FastAPI(
    title="Atlas Accounts Service",
    version="1.0.0",
    description="Authentication, licensing, analytics and admin for Atlas desktop.",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "atlas-accounts"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("accounts_service.main:app", host=SERVICE_HOST, port=SERVICE_PORT, reload=False)
