from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import InvalidKeyError, ObjectNotFoundError, Storage, StorageError
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> LocalStorage:
    settings = get_settings()
    # STORAGE_DRIVER=local é o único driver por enquanto (VPS própria).
    return LocalStorage(settings.storage_local_path, settings.jwt_secret)


__all__ = [
    "InvalidKeyError",
    "LocalStorage",
    "ObjectNotFoundError",
    "Storage",
    "StorageError",
    "get_storage",
]
