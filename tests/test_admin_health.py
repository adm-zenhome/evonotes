import json

FORBIDDEN = ["localhost", "127.0.0.1", "8080", "8765", "sqlite", "openai", "elevenlabs", "resend", "/home", ".db"]


def test_health_shape(client):
    r = client.get("/api/admin/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degradado", "fora"}
    assert {"nome_publico": "Banco de dados", "status": "ok"} in body["componentes"]
    for c in body["componentes"]:
        assert set(c) == {"nome_publico", "status"}


def test_health_no_internal_leak(client):
    text = json.dumps(client.get("/api/admin/health").json()).lower()
    for word in FORBIDDEN:
        assert word not in text


def test_admin_404_standard_error(client):
    r = client.get("/api/admin/nao-existe")
    assert r.status_code == 404
    assert r.json() == {"code": "nao_encontrado", "message": "Recurso não encontrado."}


def test_legacy_routes_untouched(client):
    assert client.get("/api/meetings").status_code == 200
