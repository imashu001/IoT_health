from typing import Any
from fastapi import HTTPException

from database import db
from utility.model import IoTDataCreate, UserCreate, UserUpdate
from utility.connectionmanage import manager
from datetime import datetime

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