import pytest
import asyncio

from unittest.mock import patch, AsyncMock, MagicMock
from datetime import timedelta
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import utility.dbutils as dbutils
from utility.model import IoTDataCreate, UserCreate, UserUpdate


def unix_ts():
    import time
    return int(time.time())


@pytest.mark.asyncio
async def test_ingest_invalid_payload_raises():
    # missing required fields for IoTDataCreate
    bad = {"user_id": "U1", "metric_1": -1}
    with pytest.raises(HTTPException):
        await dbutils.ingest_iot_data(bad)


@pytest.mark.asyncio
@patch("utility.dbutils.get_active_user", new_callable=AsyncMock)
async def test_ingest_inactive_user_propagates(mock_active):
    mock_active.side_effect = HTTPException(status_code=400, detail="User is not active")
    valid = {"user_id": "U1", "metric_1": 10, "metric_2": 20, "metric_3": 5, "timestamp": unix_ts()}
    with pytest.raises(HTTPException):
        await dbutils.ingest_iot_data(valid)


@pytest.mark.asyncio
@patch("utility.dbutils.db.users.find_one", new_callable=AsyncMock)
async def test_get_user_or_404_not_found(mock_find):
    mock_find.return_value = None
    with pytest.raises(HTTPException) as exc:
        await dbutils.get_user_or_404("nope")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@patch("utility.dbutils.get_user_or_404", new_callable=AsyncMock)
async def test_get_active_user_inactive(mock_get):
    mock_get.return_value = {"user_id": "U1", "status": "inactive"}
    with pytest.raises(HTTPException) as exc:
        await dbutils.get_active_user("U1")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
@patch("utility.dbutils.get_active_user", new_callable=AsyncMock)
async def test_get_latest_iot_no_data(mock_active):
    mock_active.return_value = {"user_id": "U1", "status": "active"}
    # replace the db with a simple MagicMock whose collection methods are AsyncMocks
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.iot_data = MagicMock()
    mock_db.iot_data.find_one = AsyncMock(return_value=None)
    with patch("utility.dbutils.db", mock_db):
        with pytest.raises(HTTPException) as exc:
            await dbutils.get_latest_iot("U1")
        assert exc.value.status_code == 404


@pytest.mark.asyncio
@patch("utility.dbutils.get_active_user", new_callable=AsyncMock)
async def test_get_iot_history_empty(mock_active):
    mock_active.return_value = {"user_id": "U1", "status": "active"}
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = []
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.iot_data = MagicMock()
    # make find().sort().limit() chain return our mock_cursor
    find_mock = MagicMock()
    find_mock.sort.return_value.limit.return_value = mock_cursor
    mock_db.iot_data.find = MagicMock(return_value=find_mock)
    with patch("utility.dbutils.db", mock_db):
        res = await dbutils.get_iot_history("U1", limit=5)
        assert res == []


@pytest.mark.asyncio
async def test_create_user_in_db():
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.users = MagicMock()
    mock_db.users.insert_one = AsyncMock(return_value=AsyncMock(inserted_id="xyz"))
    user = UserCreate(user_id="U1", name="A", status="active", created_by="admin")
    with patch("utility.dbutils.db", mock_db):
        res = await dbutils.create_user_in_db(user)
        assert res["id"] == "xyz"


@pytest.mark.asyncio
async def test_update_user_in_db_no_fields():
    with pytest.raises(HTTPException) as exc:
        await dbutils.update_user_in_db("U1", UserUpdate())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_user_in_db_not_found():
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.users = MagicMock()
    mock_db.users.update_one = AsyncMock(return_value=AsyncMock(matched_count=0))
    with patch("utility.dbutils.db", mock_db):
        with pytest.raises(HTTPException) as exc:
            await dbutils.update_user_in_db("U1", UserUpdate(name="B"))
        assert exc.value.status_code == 404


def test_authenticate_user_true_false():
    assert dbutils.authenticate_user("admin", "password") is True
    assert dbutils.authenticate_user("no", "no") is False


def test_create_and_decode_token_sync():
    token = dbutils.create_access_token("U1", expires_delta=timedelta(minutes=1))
    # decode via sync wrapper using asyncio.run
    decoded = asyncio.run(dbutils.decode_jwt_token(token))
    assert decoded == "U1"


@pytest.mark.asyncio
async def test_decode_jwt_token_with_bearer_prefix():
    token = dbutils.create_access_token("U2", expires_delta=timedelta(minutes=1))
    pref = "Bearer " + token
    res = await dbutils.decode_jwt_token(pref)
    assert res == "U2"


@pytest.mark.asyncio
async def test_verify_jwt_invalid():
    bad_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="badtoken")
    with pytest.raises(HTTPException):
        await dbutils.verify_jwt(bad_creds)
