from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.core.errors import AppError, NotFoundError
from app.storage import InvalidKeyError, LocalStorage, get_storage

router = APIRouter(tags=["files"])


@router.get("/files/{key:path}", include_in_schema=False)
async def serve_file(
    key: str,
    exp: int = Query(...),
    sig: str = Query(...),
    storage: LocalStorage = Depends(get_storage),
):
    """Serve um arquivo do storage local a partir de uma URL assinada."""
    try:
        path = storage.path_for(key)
    except InvalidKeyError as exc:
        raise NotFoundError() from exc
    if not storage.verify_signature(key, exp, sig):
        raise AppError("invalid_signature", "Link inválido ou expirado.", 403)
    if not path.is_file():
        raise NotFoundError()
    return FileResponse(
        path,
        media_type=storage.guess_type(key),
        headers={"Cache-Control": "private, max-age=300"},
    )
