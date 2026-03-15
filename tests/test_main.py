import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello FastAPI"}


def test_login_success_and_failure():
    # correct credentials
    r = client.post("/auth/login", json={"username": "admin", "password": "password"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    # wrong credentials
    r2 = client.post("/auth/login", json={"username": "no", "password": "no"})
    assert r2.status_code == 401


@pytest.mark.parametrize("path,payload,patch_target,return_value,expect", [
    ("/users", {"user_id": "U1", "name": "A", "status": "active", "created_by": "admin"}, "create_user_in_db", {"id": "abc"}, 200),
    ("/users/U1", {"name": "B"}, "update_user_in_db", {"message": "User updated"}, 200),
])
def test_user_endpoints_patch(path, payload, patch_target, return_value, expect):
    async_mock = AsyncMock(return_value=return_value)
    headers = {"Authorization": "Bearer tok"}
    with patch.object(main, patch_target, new=async_mock):
        main.app.dependency_overrides[main.verify_jwt] = lambda: 'admin'
        try:
            r = client.post(path, json=payload, headers=headers) if path == "/users" else client.put(path, json=payload, headers=headers)
        finally:
            main.app.dependency_overrides.pop(main.verify_jwt, None)
        assert r.status_code == expect


def test_get_user_and_latest_and_history():
    # Patch get_user_or_404
    headers = {"Authorization": "Bearer tok"}
    with patch.object(main, 'get_user_or_404', new=AsyncMock(return_value={"_id": "oid", "user_id": "U1"})):
        main.app.dependency_overrides[main.verify_jwt] = lambda: 'admin'
        try:
            r = client.get('/users/U1', headers=headers)
        finally:
            main.app.dependency_overrides.pop(main.verify_jwt, None)
        assert r.status_code == 200
        assert r.json()["user"]["_id"] == "oid"

    # Patch get_latest_iot
    with patch.object(main, 'get_latest_iot', new=AsyncMock(return_value={"_id": "d1", "user_id": "U1"})):
        main.app.dependency_overrides[main.verify_jwt] = lambda: 'admin'
        try:
            r2 = client.get('/users/U1/iot/latest', headers=headers)
        finally:
            main.app.dependency_overrides.pop(main.verify_jwt, None)
        assert r2.status_code == 200
        assert r2.json()["_id"] == "d1"

    # Patch get_iot_history
    sample = [{"_id": "h1"}, {"_id": "h2"}]
    with patch.object(main, 'get_iot_history', new=AsyncMock(return_value=sample)):
        main.app.dependency_overrides[main.verify_jwt] = lambda: 'admin'
        try:
            r3 = client.get('/users/U1/iot/history?limit=2', headers=headers)
        finally:
            main.app.dependency_overrides.pop(main.verify_jwt, None)
        assert r3.status_code == 200
        assert r3.json()["data"] == sample


def test_create_iot_data_endpoint():
    payload = {"user_id": "U1", "metric_1": 10, "metric_2": 20, "metric_3": 5, "timestamp": int(1620000000)}
    headers = {"Authorization": "Bearer tok"}
    with patch.object(main, 'ingest_iot_data', new=AsyncMock(return_value={"_id": "newid"})):
        main.app.dependency_overrides[main.verify_jwt] = lambda: 'admin'
        try:
            r = client.post('/iot/data', json=payload, headers=headers)
        finally:
            main.app.dependency_overrides.pop(main.verify_jwt, None)
        assert r.status_code == 200
        assert r.json()["id"] == "newid"


def test_websocket_subscribe_accepts_and_disconnects():
    # Patch decode_jwt_token and manager
    async_decode = AsyncMock(return_value='U1')
    mock_manager = MagicMock()
    # make connect accept the websocket so server can proceed
    async def connect_side_effect(user_id, websocket):
        await websocket.accept()
    mock_manager.connect = AsyncMock(side_effect=connect_side_effect)
    mock_manager.disconnect = MagicMock()

    with patch.object(main, 'decode_jwt_token', new=async_decode), patch.object(main, 'manager', new=mock_manager):
        with client.websocket_connect('/ws/subscribe?user_id=U1', headers={"authorization": "Bearer tok"}) as ws:
            ws.send_text("ping")
            ws.close()
        mock_manager.connect.assert_called()
