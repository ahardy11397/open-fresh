"""Application factory: wires the per-request DB connection dependency.

The DB path comes from the ``OPENFRESH_DB`` environment variable, defaulting
to ``./openfresh.db``; a ``db_path`` argument overrides both (used by tests).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from openfresh import api, db

DEFAULT_DB_PATH = "./openfresh.db"
DEFAULT_FALLBACK_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Open-fresh</title></head><body>"
    '<div id="root">Open-fresh Web UI</div></body></html>'
)


def create_app(
    db_path: str | None = None,
    static_dir: str | None = None,
) -> FastAPI:
    """Build a FastAPI app against the given (or env-configured) database."""
    resolved_db = db_path or os.environ.get("OPENFRESH_DB") or DEFAULT_DB_PATH

    static_candidate = static_dir or os.environ.get("OPENFRESH_STATIC_DIR")
    if static_candidate:
        resolved_static = Path(static_candidate)
    elif Path("/app/static").exists():
        resolved_static = Path("/app/static")
    else:
        resolved_static = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.get_conn(resolved_db)
        db.init_db(conn)
        try:
            yield conn
        finally:
            conn.close()

    app = FastAPI(title="openfresh")

    # Register API router FIRST so API routes take priority over static mounts.
    app.include_router(api.build_router(get_conn))

    if resolved_static.is_dir() and (resolved_static / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(resolved_static / "assets")),
            name="assets",
        )

    @app.get("/", include_in_schema=False)
    def root():
        if resolved_static.is_dir() and (resolved_static / "index.html").is_file():
            return FileResponse(str(resolved_static / "index.html"))
        return HTMLResponse(DEFAULT_FALLBACK_HTML)

    return app


__all__ = ["create_app"]
