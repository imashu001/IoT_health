from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect,Depends, Header
from database import db
from utility.model import UserCreate, UserUpdate, IoTDataCreate, LoginRequest
from utility.connectionmanage import manager
from utility.dbutils import get_user_or_404, get_active_user, ingest_iot_data, get_latest_iot, get_iot_history, create_user_in_db, update_user_in_db, verify_jwt, authenticate_user, create_access_token, decode_jwt_token
from fastapi import Body


app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}


@app.post("/auth/login")
async def login(payload: LoginRequest):
    username = payload.username
    password = payload.password

    if not authenticate_user(username, password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_access_token(user_id=username)
    return {"access_token": token}


@app.get("/users/{user_id}")
async def get_user(user_id: str, _: str = Depends(verify_jwt)):
    user = await get_user_or_404(user_id)
    user["_id"] = str(user["_id"])
    return {"user": user}


@app.post("/users")
async def create_user(user: UserCreate, _: str = Depends(verify_jwt)):
    return await create_user_in_db(user)


@app.put("/users/{user_id}")
async def update_user(user_id: str, user: UserUpdate,  _: str = Depends(verify_jwt)):
    return await update_user_in_db(user_id, user)

@app.post("/iot/data")
async def create_iot_data(data: IoTDataCreate,  _: str = Depends(verify_jwt)):
    doc = await ingest_iot_data(data.model_dump())
    return {"message": "IoT data inserted successfully", "id": doc["_id"]}

@app.get("/users/{user_id}/iot/latest")
async def latest_iot(user_id: str,  _: str = Depends(verify_jwt)):
    return await get_latest_iot(user_id)

@app.get("/users/{user_id}/iot/history")
async def iot_history(user_id: str, limit: int = 50,  _: str = Depends(verify_jwt)):
    data = await get_iot_history(user_id, limit)
    return {"data": data}

@app.websocket("/ws/ingest")
async def websocket_ingest(websocket: WebSocket):
    token = websocket.headers.get("authorization")
    if not token:
        await websocket.close(code=1008)  # Missing token
        return

    # Validate token on connect
    try:
        user_id = await decode_jwt_token(token)
    except HTTPException:
        await websocket.close(code=4001)  # Invalid/expired token
        return

    await websocket.accept()
    try:
        while True:
            # Re-validate token on each message
            try:
                await decode_jwt_token(token)
            except HTTPException:
                await websocket.close(code=4001)  # Disconnect if token expired
                break

            data = await websocket.receive_json()
            try:
                await ingest_iot_data(data)
            except HTTPException as e:
                await websocket.send_json({"error": e.detail})

    except WebSocketDisconnect:
        print(f"Ingest WS disconnected for user {user_id}")


@app.websocket("/ws/subscribe")
async def websocket_subscribe(websocket: WebSocket, user_id: str):
    token = websocket.headers.get("authorization")
    if not token:
        await websocket.close(code=1008)
        return

    # Only check token on connect (don't close on ingest token expiry)
    try:
        await decode_jwt_token(token)
    except HTTPException:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)