"""Application factory: wires the per-request DB connection dependency.

The DB path comes from the ``OPENFRESH_DB`` environment variable, defaulting
to ``./openfresh.db``; a ``db_path`` argument overrides both (used by tests).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator

from fastapi import FastAPI

from openfresh import api, db

DEFAULT_DB_PATH = "./openfresh.db"


def create_app(db_path: str | None = None) -> FastAPI:
    """Build a FastAPI app against the given (or env-configured) database."""
    resolved = db_path or os.environ.get("OPENFRESH_DB") or DEFAULT_DB_PATH

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.get_conn(resolved)
        db.init_db(conn)
        try:
            yield conn
        finally:
            conn.close()

    app = FastAPI(title="openfresh")
    app.include_router(api.build_router(get_conn))
    return app


__all__ = ["create_app"]
