from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse() -> None:
    response = client.post(
        "/parse",
        json={"text": "Hola. Yo hablo español.", "language": "es"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "sentences" in payload
    assert len(payload["sentences"]) >= 1
