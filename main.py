
from contextlib import asynccontextmanager

import sqlalchemy
from typing import Annotated
from uuid import uuid4

from redis.asyncio import ConnectionPool, Redis
from app.db import AsyncSession, get_db
from app.models import User
from app.routers import auth, chat
from fastapi import Depends, FastAPI, UploadFile, HTTPException
from app.auth.jwt import get_current_user
from pinecone import Pinecone
from unstructured.chunking.title import chunk_by_title
from unstructured.partition.auto import partition
from app.llm import get_dense_embeddings, get_sparse_embeddings, index
from app.services import get_redis, init_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    # await close_redis()

app = FastAPI(lifespan=lifespan)

app.include_router(auth.router) 
app.include_router(chat.router)


CurrentUser = Annotated[User, Depends(get_current_user)]
Db = Annotated[AsyncSession, Depends(get_db)]

@app.get("/redis")
async def check_redis():
    redis = get_redis()
    value = await redis.get("working")
    if not value:
        await redis.set("working", "redis is up")
        value = "redis is up"
    return {"value": value}

@app.get("/me")
async def get_me(user : CurrentUser):

    response = {"id" : user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at}

    return response

@app.post("/upload")
async def upload_file(file: UploadFile, user : CurrentUser):
    try:

        # TODO: Celery + redis
        elements = partition(file=file.file)
        chunks = chunk_by_title(elements=elements, max_characters=500, overlap=100)
        formatted_chunks = [chunk.text for chunk in chunks]

        dense = get_dense_embeddings(content=formatted_chunks)
        sparse = get_sparse_embeddings(content=formatted_chunks, input_type="passage")

        vectors =[]
        for i, chunk in enumerate(formatted_chunks):
            formatted = {
                "id" : str(uuid4()),
                "values": dense[i],
                "sparse_values": sparse[i],
                "metadata" :{
                    "text": chunk,
                    "file": file.filename,
                    "user_id": str(user.id) 
                }
            }
            vectors.append(formatted)

        result = index.upsert(vectors=vectors)
        
        return  { 
            "success": True,
            "chunks_uploaded": result.upserted_count
            }


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
