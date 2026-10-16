"""Storage em disco local (dev e produção na VPS, em volume Docker com backup)."""

import asyncio
import hashlib
import hmac
import mimetypes
import os
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode

from app.storage.base import InvalidKeyError, ObjectNotFoundError


def _validate_key(key: str) -> str:
    if not key or key.startswith("/") or "//" in key or "\\" in key or "\x00" in key:
        raise InvalidKeyError(key)
    parts = PurePosixPath(key).parts
    if any(p in ("..", ".", "") for p in parts):
        raise InvalidKeyError(key)
    return key


class LocalStorage:
    def __init__(self, root: str | Path, secret: str, url_base: str = "/api/v1/files"):
        self.root = Path(root).resolve()
        self._secret = secret.encode()
        self.url_base = url_base.rstrip("/")

    def path_for(self, key: str) -> Path:
        path = (self.root / _validate_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidKeyError(key)
        return path

    # ---- operações ---------------------------------------------------------

    def _put_sync(self, key: str, data: bytes) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # escrita atômica: arquivo temporário no mesmo diretório + os.replace
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._put_sync, key, data)

    async def get(self, key: str) -> bytes:
        path = self.path_for(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(key) from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.path_for(key).unlink, True)

    def _delete_prefix_sync(self, prefix: str) -> int:
        target = self.path_for(prefix.rstrip("/"))
        if target.is_file():
            target.unlink()
            return 1
        if not target.is_dir():
            return 0
        count = sum(1 for p in target.rglob("*") if p.is_file())
        shutil.rmtree(target)
        return count

    async def delete_prefix(self, prefix: str) -> int:
        return await asyncio.to_thread(self._delete_prefix_sync, prefix)

    async def healthcheck(self) -> bool:
        def _check() -> bool:
            self.root.mkdir(parents=True, exist_ok=True)
            return os.access(self.root, os.W_OK)

        return await asyncio.to_thread(_check)

    # ---- URLs assinadas ----------------------------------------------------

    def _signature(self, key: str, exp: int) -> str:
        msg = f"{key}:{exp}".encode()
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def signed_url(self, key: str, expires_in: int = 3600) -> str:
        _validate_key(key)
        exp = int(time.time()) + expires_in
        query = urlencode({"exp": exp, "sig": self._signature(key, exp)})
        return f"{self.url_base}/{quote(key)}?{query}"

    def verify_signature(self, key: str, exp: int, sig: str) -> bool:
        if exp < int(time.time()):
            return False
        return hmac.compare_digest(self._signature(key, exp), sig)

    @staticmethod
    def guess_type(key: str) -> str:
        return mimetypes.guess_type(key)[0] or "application/octet-stream"
