from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from database import db
from datetime import datetime
from utility.model import UserCreate, UserUpdate, IoTDataCreate
from utility.connectionmanage import manager

now = datetime.utcnow()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}

@app.get("/db-test")
async def test_db():
    collections = await db.list_collection_names()
    return {"collections": collections}

@app.get("/users/{user_id}")
async def get_user(user_id: str):

    user = await db.users.find_one({"user_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["_id"] = str(user["_id"])

    return {"user": user}


@app.post("/users")
async def create_user(user: UserCreate):
    now = datetime.utcnow()

    doc = {
        "user_id": user.user_id,
        "name": user.name,
        "status": user.status,
        "created_by": user.created_by,
        "created_at": now,
        "updated_at": now
    }

    result = await db.users.insert_one(doc)

    return {
        "message": "User inserted",
        "id": str(result.inserted_id)
    }

@app.put("/users/{user_id}")
async def update_user(user_id: str, user: UserUpdate):

    update_data = user.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided")

    update_data["updated_at"] = datetime.utcnow()

    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated"}

@app.post("/iot/data")
async def create_iot_data(data: IoTDataCreate):
    current_timestamp = int(datetime.utcnow().timestamp())

    if data.timestamp > current_timestamp:
        raise HTTPException(
            status_code=400,
            detail="timestamp cannot be in the future"
        )

    user = await db.users.find_one({"user_id": data.user_id})

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User does not exist"
        )
    if user["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="User is not active"
        )
    doc = data.model_dump()

    result = await db.iot_data.insert_one(doc)

    doc["_id"] = str(result.inserted_id)

    await manager.broadcast(
        data.user_id,
        {
            "event": "NEW_DATA",
            "data": doc
        }
    )

    return {
        "message": "IoT data inserted successfully",
        "id": str(result.inserted_id)
    }

@app.get("/users/{user_id}/iot/latest")
async def get_latest_iot(user_id: str):

    # check user exists
    user = await db.users.find_one({"user_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await db.iot_data.find_one(
        {"user_id": user_id},
        sort=[("timestamp", -1)]
    )

    if not data:
        raise HTTPException(status_code=404, detail="No IoT data found")

    data["_id"] = str(data["_id"])

    return data

@app.get("/users/{user_id}/iot/history")
async def get_iot_history(user_id: str, limit: int = 50):

    # check user exists
    user = await db.users.find_one({"user_id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cursor = db.iot_data.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(limit)

    data = await cursor.to_list(limit)

    for d in data:
        d["_id"] = str(d["_id"])

    return {"data": data}


@app.websocket("/ws/ingest")
async def websocket_ingest(websocket: WebSocket):

    await websocket.accept()

    try:
        while True:

            data = await websocket.receive_json()

            try:
                iot = IoTDataCreate(**data)
            except Exception as e:
                await websocket.send_json({"error": str(e)})
                continue

            current_ts = int(datetime.utcnow().timestamp())

            if iot.timestamp > current_ts:
                await websocket.send_json({"error": "timestamp cannot be in the future"})
                continue

            user = await db.users.find_one({"user_id": iot.user_id})

            if not user:
                await websocket.send_json({"error": "User does not exist"})
                continue

            if user["status"] != "active":
                await websocket.send_json({"error": "User is not active"})
                continue

            doc = iot.model_dump()

            result = await db.iot_data.insert_one(doc)

            doc["_id"] = str(result.inserted_id)

            await manager.broadcast(
                iot.user_id,
                {
                    "event": "NEW_DATA",
                    "data": doc
                }
            )

    except WebSocketDisconnect:
        pass

@app.websocket("/ws/subscribe")
async def websocket_subscribe(websocket: WebSocket, user_id: str):

    await manager.connect(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)