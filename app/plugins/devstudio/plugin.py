from __future__ import annotations

import logging
from fastapi import FastAPI
from app.plugins.devstudio.main import router

logger = logging.getLogger(__name__)


def register(app: FastAPI) -> None:
    app.include_router(router)
    logger.info("✅ Plugin 'devstudio' (VlahX Cloud DevStudio & Web IDE) înregistrat cu succes!")
