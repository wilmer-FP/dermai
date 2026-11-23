from app import __version__


def test_health_returns_ok(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "DermAI",
        "version": __version__,
        "environment": "testing",
        "demo_mode": False,
        "demo_retention_hours": None,
    }


def test_openapi_schema_is_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
