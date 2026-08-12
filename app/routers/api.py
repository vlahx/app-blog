from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.db import get_db

router = APIRouter()


@router.get("/")
def api_root():
    return {
        "service": "camionagiul-blog",
        "health": "/api/status",
    }


@router.get("/status")
def api_status(response: Response, db: Session = Depends(get_db)):
    """Răspuns pentru monitorizare: verificare conexiune SQLite."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    payload = {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "camionagiul-blog",
        "checks": {"database": "ok" if db_ok else "error"},
    }
    if not db_ok:
        response.status_code = 503
    return payload
