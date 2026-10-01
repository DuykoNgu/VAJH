from tests.conftest import running_app


async def test_liveness(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_ready_when_dependencies_up(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["postgres"] == "ok" and r.json()["checks"]["redis"] == "ok"


async def test_ready_reports_redis_down():
    async with running_app(redis_url="redis://localhost:6390/0") as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    checks = r.json()["checks"]
    assert checks["redis"].startswith("error") and checks["postgres"] == "ok"
