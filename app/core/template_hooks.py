from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)

_post_article_footer: list[tuple[int, Callable[[Any, Request], str]]] = []
_post_header_meta: list[tuple[int, Callable[[Any, Request], str]]] = []


def clear_post_article_footers() -> None:
    _post_article_footer.clear()
    _post_header_meta.clear()


def register_post_article_footer(
    renderer: Callable[[Any, Request], str],
    *,
    order: int = 100,
) -> None:
    _post_article_footer.append((order, renderer))
    _post_article_footer.sort(key=lambda t: t[0])


def render_post_article_footers(post: Any, request: Request) -> str:
    parts: list[str] = []
    for _, fn in _post_article_footer:
        try:
            chunk = (fn(post, request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("post_article_footer renderer failed")
    return "\n".join(parts)


def register_post_header_meta(
    renderer: Callable[[Any, Request], str],
    *,
    order: int = 100,
) -> None:
    _post_header_meta.append((order, renderer))
    _post_header_meta.sort(key=lambda t: t[0])


def render_post_header_metas(post: Any, request: Request) -> str:
    parts: list[str] = []
    for _, fn in _post_header_meta:
        try:
            chunk = (fn(post, request) or "").strip()
            if chunk:
                parts.append(chunk)
        except Exception:
            logger.exception("post_header_meta renderer failed")
    return " ".join(parts)
