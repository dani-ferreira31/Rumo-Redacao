from typing import Protocol


class StorageError(Exception):
    pass


class InvalidKeyError(StorageError):
    pass


class ObjectNotFoundError(StorageError):
    pass


class Storage(Protocol):
    """Armazenamento de arquivos. Chaves de usuário seguem `users/{user_id}/...`."""

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> int: ...

    def signed_url(self, key: str, expires_in: int = 3600) -> str: ...

    async def healthcheck(self) -> bool: ...
