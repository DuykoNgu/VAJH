async def test_allowed_origin_may_send_dev_user_header(client):
    pre = await client.options("/health", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-dev-user"})
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-dev-user" in pre.headers["access-control-allow-headers"].lower()
    r = await client.get("/health", headers={"Origin": "http://localhost:3000", "X-Dev-User": "minh5a"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in r.headers


async def test_unknown_origin_not_allowed(client):
    r = await client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
