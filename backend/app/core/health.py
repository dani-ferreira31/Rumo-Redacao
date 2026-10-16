import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.storage import LocalStorage, get_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    result = {"db": "ok", "storage": "ok"}
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health_db_error")
        result["db"] = "error"
    try:
        if not await storage.healthcheck():
            result["storage"] = "error"
    except Exception:
        logger.exception("health_storage_error")
        result["storage"] = "error"
    ok = all(v == "ok" for v in result.values())
    return JSONResponse(result, status_code=200 if ok else 503)
