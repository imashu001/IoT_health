import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from fastapi.testclient import TestClient
import main


client = TestClient(main.app)


def test_ws_ingest_missing_token_connect_closes():
    # connecting without Authorization should result in immediate close
    with pytest.raises(Exception):
        with client.websocket_connect('/ws/ingest') as ws:
            pass


def test_ws_ingest_invalid_token_closes():
    # decode_jwt_token raises HTTPException on connect
    async_mock = AsyncMock(side_effect=HTTPException(status_code=401))
    with patch.object(main, 'decode_jwt_token', new=async_mock):
        with pytest.raises(Exception):
            with client.websocket_connect('/ws/ingest', headers={"authorization": "Bearer bad"}) as ws:
                pass


def test_ws_ingest_ingest_error_sends_error_json():
    # decode_jwt_token returns user, ingest_iot_data raises HTTPException with detail
    async_decode = AsyncMock(return_value='U1')
    async_ingest = AsyncMock(side_effect=HTTPException(status_code=400, detail='bad data'))

    with patch.object(main, 'decode_jwt_token', new=async_decode), patch.object(main, 'ingest_iot_data', new=async_ingest):
        with client.websocket_connect('/ws/ingest', headers={"authorization": "Bearer tok"}) as ws:
            # send a JSON payload; server should respond with error JSON
            ws.send_json({"user_id": "U1", "metric_1": 1, "metric_2": 2, "metric_3": 3, "timestamp": 1620000000})
            resp = ws.receive_json()
            assert resp == {"error": "bad data"}


def test_ws_ingest_token_expires_after_connect():
    # decode_jwt_token should succeed on first call, then raise on second
    async_decode = AsyncMock(side_effect=["U1", HTTPException(status_code=401)])
    async_ingest = AsyncMock(return_value={"_id": "ok"})

    with patch.object(main, 'decode_jwt_token', new=async_decode), patch.object(main, 'ingest_iot_data', new=async_ingest):
        with pytest.raises(Exception):
            with client.websocket_connect('/ws/ingest', headers={"authorization": "Bearer tok"}) as ws:
                # first send triggers re-validation which will raise and close
                ws.send_json({"user_id": "U1", "metric_1": 1, "metric_2": 2, "metric_3": 3, "timestamp": 1620000000})
                # attempt to receive; connection should be closed by server
                ws.receive_text()


def test_ws_ingest_disconnect_triggers_handler():
    async_decode = AsyncMock(return_value='U1')
    with patch.object(main, 'decode_jwt_token', new=async_decode):
        with patch('builtins.print') as mock_print:
            with client.websocket_connect('/ws/ingest', headers={"authorization": "Bearer tok"}) as ws:
                # close from client side to trigger server-side WebSocketDisconnect
                ws.close()
            # server should have printed the disconnect message
            mock_print.assert_called()


@pytest.mark.asyncio
async def test_websocket_ingest_direct_error_and_disconnect():
    # Directly call the websocket_ingest coroutine with a fake websocket to cover send_json and disconnect handler.
    from starlette.websockets import WebSocketDisconnect

    class FakeHeaders:
        def __init__(self, d):
            self._d = d
        def get(self, k, default=None):
            return self._d.get(k, default)

    class FakeWebSocket:
        def __init__(self):
            self.headers = FakeHeaders({'authorization': 'Bearer tok'})
            self.accept = AsyncMock()
            self.send_json = AsyncMock()
            self.close = AsyncMock()
            self._recv_calls = 0

        async def receive_json(self):
            if self._recv_calls == 0:
                self._recv_calls += 1
                return {"user_id": "U1", "metric_1": 1, "metric_2": 2, "metric_3": 3, "timestamp": 1620000000}
            # after first message, simulate client disconnect
            raise WebSocketDisconnect()

        async def receive_text(self):
            raise WebSocketDisconnect()

    fake_ws = FakeWebSocket()

    async_decode = AsyncMock(return_value='U1')
    async_ingest = AsyncMock(side_effect=HTTPException(status_code=400, detail='bad data'))

    with patch.object(main, 'decode_jwt_token', new=async_decode), patch.object(main, 'ingest_iot_data', new=async_ingest), patch('builtins.print') as mock_print:
        await main.websocket_ingest(fake_ws)
        # ensure send_json was called with the error detail
        fake_ws.send_json.assert_called_with({"error": "bad data"})
        # ensure disconnect handler printed
        mock_print.assert_called()
