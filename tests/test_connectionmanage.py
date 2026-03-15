import pytest
from unittest.mock import AsyncMock
from utility.connectionmanage import ConnectionManager

@pytest.mark.asyncio
async def test_connect_disconnect_broadcast():
    manager = ConnectionManager()

    # Mock websocket
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    user_id = "U1001"

    # Connect
    await manager.connect(user_id, ws1)
    await manager.connect(user_id, ws2)

    assert user_id in manager.active_connections
    assert len(manager.active_connections[user_id]) == 2

    # Broadcast
    message = {"event": "TEST"}
    await manager.broadcast(user_id, message)

    ws1.send_json.assert_awaited_with(message)
    ws2.send_json.assert_awaited_with(message)

    # Disconnect one websocket
    manager.disconnect(user_id, ws1)
    assert len(manager.active_connections[user_id]) == 1

    # Disconnect second websocket
    manager.disconnect(user_id, ws2)
    assert user_id not in manager.active_connections