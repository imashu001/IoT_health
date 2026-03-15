from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from database import db
from utility.model import UserCreate, UserUpdate, IoTDataCreate
from utility.connectionmanage import manager
from utility.dbutils import get_user_or_404, get_active_user, ingest_iot_data, get_latest_iot, get_iot_history, create_user_in_db, update_user_in_db

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await get_user_or_404(user_id)
    user["_id"] = str(user["_id"])
    return {"user": user}


@app.post("/users")
async def create_user(user: UserCreate):
    return await create_user_in_db(user)


@app.put("/users/{user_id}")
async def update_user(user_id: str, user: UserUpdate):
    return await update_user_in_db(user_id, user)

@app.post("/iot/data")
async def create_iot_data(data: IoTDataCreate):
    doc = await ingest_iot_data(data.model_dump())
    return {"message": "IoT data inserted successfully", "id": doc["_id"]}

@app.get("/users/{user_id}/iot/latest")
async def latest_iot(user_id: str):
    return await get_latest_iot(user_id)

@app.get("/users/{user_id}/iot/history")
async def iot_history(user_id: str, limit: int = 50):
    data = await get_iot_history(user_id, limit)
    return {"data": data}

@app.websocket("/ws/ingest")
async def websocket_ingest(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                await ingest_iot_data(data)
            except HTTPException as e:
                await websocket.send_json({"error": e.detail})
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