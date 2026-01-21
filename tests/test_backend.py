import json
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def create_defaults(tmp_path: Path) -> None:
    default_settings = {
        "create_paid_users": False,
        "next_step_delay": {"type": "Fixed time", "value": 3600},
        "messages": {"welcome_message": "Hi"},
    }
    default_script = [
        {
            "title": "Step 1",
            "description": "Test",
            "content": [{"type": "text", "value": "Hello"}],
        }
    ]
    (tmp_path / "default_settings.json").write_text(
        json.dumps(default_settings, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    (tmp_path / "test_script.json").write_text(
        json.dumps(default_script, ensure_ascii=False, indent=4), encoding="utf-8"
    )


def create_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("DB_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    create_defaults(tmp_path)
    backend = importlib.import_module("backend")
    importlib.reload(backend)
    return TestClient(backend.app)


def test_healthcheck(monkeypatch, tmp_path):
    client = create_client(monkeypatch, tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_roundtrip(monkeypatch, tmp_path):
    client = create_client(monkeypatch, tmp_path)
    response = client.get("/settings")
    assert response.status_code == 200
    payload = response.json()
    payload["create_paid_users"] = True
    save_response = client.put("/settings", json=payload)
    assert save_response.status_code == 200
    reload_response = client.get("/settings")
    assert reload_response.json()["create_paid_users"] is True


def test_script_roundtrip(monkeypatch, tmp_path):
    client = create_client(monkeypatch, tmp_path)
    response = client.get("/script")
    assert response.status_code == 200
    script = response.json()
    script.append({"title": "Step 2", "description": "", "content": []})
    save_response = client.put("/script", json=script)
    assert save_response.status_code == 200
    reload_response = client.get("/script")
    assert len(reload_response.json()) == 2


def test_user_crud_and_logs(monkeypatch, tmp_path):
    client = create_client(monkeypatch, tmp_path)
    create_response = client.post("/users", json={"id": 123, "payed": False})
    assert create_response.status_code == 200
    update_response = client.patch("/users/123", json={"payed": True})
    assert update_response.status_code == 200
    assert update_response.json()["payed"] is True
    log_response = client.post(
        "/logs",
        json={"user_id": 123, "level": "info", "message": "Test log"},
    )
    assert log_response.status_code == 200
    list_logs = client.get("/logs", params={"user_id": 123})
    assert list_logs.status_code == 200
    assert len(list_logs.json()) == 1
