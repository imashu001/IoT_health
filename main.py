from fastapi import FastAPI
from database import db

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}

@app.get("/db-test")
async def test_db():
    collections = await db.list_collection_names()
    return {"collections": collections}