async def test_health(client):
    for path in ("/health", "/api/v1/health"):
        resp = await client.get(path)
        assert resp.status_code == 200
        assert resp.json() == {"db": "ok", "storage": "ok"}


async def test_404_no_formato_padrao(client):
    resp = await client.get("/api/v1/nao-existe")
    assert resp.status_code == 404
    assert resp.json() == {
        "error": {"code": "not_found", "message": "Recurso não encontrado.", "details": {}}
    }


async def test_422_no_formato_padrao(client):
    resp = await client.get("/api/v1/files/qualquer.txt")  # faltam exp e sig
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["code"] == "validation_error"
    assert {f["field"] for f in body["details"]["fields"]} == {"exp", "sig"}


async def test_request_id_no_header(client):
    resp = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"
