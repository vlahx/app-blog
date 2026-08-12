from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "plugins" / "analytics" / "analytics.db"


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_analytics_db() -> None:
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS article_analytics (
                slug TEXT PRIMARY KEY,
                views_count INTEGER DEFAULT 0,
                total_seconds INTEGER DEFAULT 0,
                pings_count INTEGER DEFAULT 0,
                updated_at TEXT
            )
        ''')
        conn.commit()


def record_ping(slug: str, seconds: int = 0, is_new_view: bool = False) -> None:
    if not slug or not slug.strip():
        return
    slug = slug.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    init_analytics_db()
    with get_db_connection() as conn:
        row = conn.execute("SELECT views_count, total_seconds, pings_count FROM article_analytics WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO article_analytics (slug, views_count, total_seconds, pings_count, updated_at) VALUES (?, ?, ?, ?, ?)",
                (slug, 1 if is_new_view else 0, max(0, seconds), 1 if seconds > 0 else 0, now_iso)
            )
        else:
            new_views = (row["views_count"] or 0) + (1 if is_new_view else 0)
            new_seconds = (row["total_seconds"] or 0) + max(0, seconds)
            new_pings = (row["pings_count"] or 0) + (1 if seconds > 0 else 0)
            conn.execute(
                "UPDATE article_analytics SET views_count = ?, total_seconds = ?, pings_count = ?, updated_at = ? WHERE slug = ?",
                (new_views, new_seconds, new_pings, now_iso, slug)
            )
        conn.commit()


def get_article_analytics(slug: str) -> dict:
    if not slug:
        return {"views": 0, "total_seconds": 0, "avg_seconds": 0}
    slug = slug.strip().lower()
    init_analytics_db()
    with get_db_connection() as conn:
        row = conn.execute("SELECT views_count, total_seconds, pings_count FROM article_analytics WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return {"views": 0, "total_seconds": 0, "avg_seconds": 0}
        views = row["views_count"] or 0
        total_sec = row["total_seconds"] or 0
        avg_sec = round(total_sec / views) if views > 0 else 0
        return {"views": views, "total_seconds": total_sec, "avg_seconds": avg_sec}


def get_all_analytics() -> list[dict]:
    init_analytics_db()
    with get_db_connection() as conn:
        rows = conn.execute("SELECT slug, views_count, total_seconds, pings_count, updated_at FROM article_analytics ORDER BY views_count DESC").fetchall()
        out = []
        for r in rows:
            views = r["views_count"] or 0
            total_sec = r["total_seconds"] or 0
            avg_sec = round(total_sec / views) if views > 0 else 0
            out.append({
                "slug": r["slug"],
                "views": views,
                "total_seconds": total_sec,
                "avg_seconds": avg_sec,
                "updated_at": r["updated_at"]
            })
        return out
