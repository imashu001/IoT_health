from typing import Any, Optional
from fastapi import HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Header
from jose import JWTError, jwt

from database import db
from utility.model import IoTDataCreate, UserCreate, UserUpdate
from utility.connectionmanage import manager
from datetime import datetime, timedelta

import os



JWT_SECRET = os.getenv("JWT_SECRET")  # same as your verify_jwt
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 10  # token validity
security = HTTPBearer()  # tells FastAPI & Swagger to use a Bearer token
async def ingest_iot_data(data: dict) -> dict:
    # Validate payload
    try:
        iot = IoTDataCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid IoT data: {e}")

    user = await get_active_user(iot.user_id)  # centralized active check

    # Insert & broadcast
    doc = iot.model_dump()
    result = await db.iot_data.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    await manager.broadcast(iot.user_id, {"event": "NEW_DATA", "data": doc})

    return doc

async def get_user_or_404(user_id: str) -> dict:
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_active_user(user_id: str) -> dict:
    user = await get_user_or_404(user_id)
    if user["status"] != "active":
        raise HTTPException(status_code=400, detail="User is not active")
    return user

async def get_latest_iot(user_id: str) -> dict:
    """
    Fetch latest IoT data for an active user.
    """
    await get_active_user(user_id)
    data = await db.iot_data.find_one({"user_id": user_id}, sort=[("timestamp", -1)])
    if not data:
        raise HTTPException(status_code=404, detail="No IoT data found")
    data["_id"] = str(data["_id"])
    return data


async def get_iot_history(user_id: str, limit: int = 50) -> list[dict]:
    """
    Fetch IoT history for an active user, limited to `limit` entries.
    """
    await get_active_user(user_id)
    cursor = db.iot_data.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    data = await cursor.to_list(limit)
    for d in data:
        d["_id"] = str(d["_id"])
    return data

async def create_user_in_db(user: UserCreate) -> dict:
    """
    Insert a new user into the DB.
    """
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
    return {"message": "User inserted", "id": str(result.inserted_id)}


async def update_user_in_db(user_id: str, user: UserUpdate) -> dict:
    """
    Update user fields in the DB.
    """
    update_data = user.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided")

    update_data["updated_at"] = datetime.utcnow()
    result = await db.users.update_one({"user_id": user_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated"}


async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Simple username/password check (replace with DB in future)
def authenticate_user(username: str, password: str) -> bool:
    # Hardcoded for example
    return username == "admin" and password == "password"

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = {"sub": user_id}
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def decode_jwt_token(token: str) -> str:
    """
    Decode JWT manually (for WebSocket)
    """
    try:
        # remove 'Bearer ' if present
        if token.lower().startswith("bearer "):
            token = token[7:]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")