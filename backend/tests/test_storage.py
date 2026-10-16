import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.storage import InvalidKeyError, LocalStorage, ObjectNotFoundError, get_storage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path, secret="s3gr3do")


async def test_put_get_delete(storage):
    await storage.put("users/u1/essays/e1/original.jpg", b"abc", "image/jpeg")
    assert await storage.get("users/u1/essays/e1/original.jpg") == b"abc"
    await storage.delete("users/u1/essays/e1/original.jpg")
    with pytest.raises(ObjectNotFoundError):
        await storage.get("users/u1/essays/e1/original.jpg")
    await storage.delete("users/u1/nao-existe.jpg")  # idempotente


async def test_delete_prefix(storage):
    await storage.put("users/u1/a.jpg", b"1", "image/jpeg")
    await storage.put("users/u1/sub/b.jpg", b"2", "image/jpeg")
    await storage.put("users/u2/c.jpg", b"3", "image/jpeg")
    assert await storage.delete_prefix("users/u1/") == 2
    assert await storage.get("users/u2/c.jpg") == b"3"
    assert await storage.delete_prefix("users/u1/") == 0


@pytest.mark.parametrize(
    "key", ["../fora.txt", "/abs.txt", "users/../../x", "users//x", "a\\b", ""]
)
async def test_bloqueia_path_traversal(storage, key):
    with pytest.raises(InvalidKeyError):
        await storage.put(key, b"x", "text/plain")


def test_assinatura(storage):
    url = storage.signed_url("users/u1/a.jpg", expires_in=60)
    qs = parse_qs(urlparse(url).query)
    exp, sig = int(qs["exp"][0]), qs["sig"][0]
    assert storage.verify_signature("users/u1/a.jpg", exp, sig)
    assert not storage.verify_signature("users/u1/b.jpg", exp, sig)
    assert not storage.verify_signature("users/u1/a.jpg", exp + 1, sig)
    assert not storage.verify_signature("users/u1/a.jpg", int(time.time()) - 1, sig)


async def test_rota_de_arquivos(client):
    storage = get_storage()
    await storage.put("users/u9/foto.jpg", b"jpeg-bytes", "image/jpeg")
    url = storage.signed_url("users/u9/foto.jpg")

    resp = await client.get(url)
    assert resp.status_code == 200
    assert resp.content == b"jpeg-bytes"
    assert resp.headers["content-type"] == "image/jpeg"

    resp = await client.get(url.replace("sig=", "sig=0"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "invalid_signature"

    expired = url.split("?")[0] + "?exp=1&sig=abc"
    assert (await client.get(expired)).status_code == 403
