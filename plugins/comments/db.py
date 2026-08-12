from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc

from app.models.db_models import Comment, User
from app.utils.db import SessionLocal, init_db as init_main_db


def init_db() -> None:
    init_main_db()


def add_comment(
    post_slug: str,
    user_id: int,
    user_name: str,
    user_avatar: Optional[str],
    content: str,
    status: str = "approved",
    parent_id: Optional[int] = None,
) -> Dict[str, Any]:
    init_db()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    with SessionLocal() as db:
        user_exists = db.query(User).filter(User.id == user_id).first()
        if not user_exists:
            first_user = db.query(User).first()
            if first_user:
                user_id = first_user.id
            else:
                new_u = User(
                    provider="telegram",
                    oauth_id=str(user_id),
                    username=user_name,
                    first_name=user_name,
                    role="reader",
                    created_at=now_dt
                )
                db.add(new_u)
                db.commit()
                db.refresh(new_u)
                user_id = new_u.id

        comment = Comment(
            post_slug=post_slug.strip(),
            parent_id=parent_id,
            user_id=user_id,
            user_name=user_name.strip(),
            user_avatar=user_avatar or "",
            content=content.strip(),
            status=status,
            created_at=now_dt,
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)

        return {
            "id": comment.id,
            "post_slug": comment.post_slug,
            "parent_id": comment.parent_id,
            "user_id": comment.user_id,
            "user_name": comment.user_name,
            "user_avatar": comment.user_avatar or "",
            "content": comment.content,
            "status": comment.status,
            "created_at": now_iso
        }


def list_comments_for_post(post_slug: str, status: str = "approved") -> List[Dict[str, Any]]:
    init_db()
    with SessionLocal() as db:
        stmt = select(Comment).where(Comment.post_slug == post_slug, Comment.status == status).order_by(Comment.id.asc())
        all_comments = db.execute(stmt).scalars().all()

        comment_dicts = [
            {
                "id": c.id,
                "post_slug": c.post_slug,
                "parent_id": c.parent_id,
                "user_id": c.user_id,
                "user_name": c.user_name,
                "user_avatar": c.user_avatar or "",
                "content": c.content,
                "status": c.status,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
                "replies": []
            }
            for c in all_comments
        ]

        by_id = {c["id"]: c for c in comment_dicts}
        top_level = []

        for c in comment_dicts:
            p_id = c["parent_id"]
            if p_id and p_id in by_id:
                by_id[p_id]["replies"].append(c)
            else:
                top_level.append(c)

        return top_level


def count_comments_for_post(post_slug: str, status: str = "approved") -> int:
    init_db()
    with SessionLocal() as db:
        stmt = select(Comment).where(Comment.post_slug == post_slug, Comment.status == status)
        return len(db.execute(stmt).scalars().all())


def list_all_comments(status: Optional[str] = None, limit: int = 150) -> List[Dict[str, Any]]:
    init_db()
    with SessionLocal() as db:
        stmt = select(Comment)
        if status and status != "all":
            stmt = stmt.where(Comment.status == status)
        stmt = stmt.order_by(desc(Comment.id)).limit(limit)
        comments = db.execute(stmt).scalars().all()
        return [
            {
                "id": c.id,
                "post_slug": c.post_slug,
                "parent_id": c.parent_id,
                "user_id": c.user_id,
                "user_name": c.user_name,
                "user_avatar": c.user_avatar or "",
                "content": c.content,
                "status": c.status,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else ""
            }
            for c in comments
        ]


def delete_comment(comment_id: int, user_id: Optional[int] = None, is_admin: bool = False) -> bool:
    init_db()
    with SessionLocal() as db:
        stmt = select(Comment).where(Comment.id == comment_id)
        comment = db.execute(stmt).scalar_one_or_none()
        if not comment:
            return False
        if not is_admin and comment.user_id != user_id:
            return False
        db.delete(comment)
        db.commit()
        return True


def update_comment_status(comment_id: int, status: str) -> bool:
    init_db()
    with SessionLocal() as db:
        stmt = select(Comment).where(Comment.id == comment_id)
        comment = db.execute(stmt).scalar_one_or_none()
        if not comment:
            return False
        comment.status = status
        db.commit()
        return True
