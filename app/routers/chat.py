import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.schema import UserCreate, UserLogin, ChatRequest
from app.db import get_db, AsyncSession
from sqlalchemy import select
from app.models import User, Conversation, Message
from app.auth import verify_password, hash_password
from app.auth.jwt import create_access_token, create_refresh_token, get_current_user
from app.llm import (ask_llm, chat, get_dense_embeddings, get_reranking, get_sparse_embeddings,
    index, rewrite_query)
from app.config import settings
from app.services import get_redis, not_ok, ok


router = APIRouter(prefix="/chat",tags=["chat"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Db = Annotated[AsyncSession, Depends(get_db)]

@router.get("/all")
async def get_all_chats(user: CurrentUser, db : Db):
   try:
        matches = await db.execute(select(Conversation).where(Conversation.user_id == user.id))
        conversations= matches.scalars().all()

        return ok({
                "user_id": user.id,
                "total": len(conversations),
                "conversations": conversations
                })
   except Exception as e:
       return not_ok("Could not load conversations. Reason: " + str(e))

@router.post("/new")
async def create_chat(user: CurrentUser, db : Db):
    try:
        conversation = Conversation(user_id=user.id, title="New chat")
        db.add(conversation)
        await db.commit()     
        await db.refresh(conversation)  
        return ok({
                "id": conversation.id,
                "title": conversation.title
                })
    except Exception as e:
        return not_ok("Could not create a new conversation. Reason: " + str(e))


@router.post("/")
async def start_chat(payload : ChatRequest, current_user : CurrentUser, db: Db ):
    try:
        redis = get_redis()
        key = payload.message + str(payload.conversation_id)
        cached = await redis.get(key)
        if cached:
            cache = await redis.get(key)
            return StreamingResponse(cache, media_type='text/plain')
        
        conversation_matches = await db.execute(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.user_id == current_user.id))
        conversation = conversation_matches.scalar_one_or_none()

        if not conversation:
            return not_ok("No chat found.")
        
        if conversation.title == "New chat":
            conversation.title = payload.message[:50]
            
        user_message = Message(conversation_id= conversation.id, content=payload.message, role="user", 
                            message_metadata={
                                "user":{
                                    "id": current_user.id,
                                }
                            })
        db.add(user_message)
        await db.flush()

        

        async def stream_llm_response():
            full_response = ""
            queries = rewrite_query(query=payload.message)
            yield json.dumps({"type": "rewrites", "data": queries}) + "\n"
            
            dense =  get_dense_embeddings(queries)
            sparse = get_sparse_embeddings(queries,"query")
            matches = []

            for i in range(len(queries)):
                result = index.query(vector=dense[i],
                                sparse_vector=sparse[i],
                                include_metadata=True,
                                top_k=10,
                                filter={
                                    "user_id": {"$eq": str(current_user.id)}
                                })
                matches.extend(result.matches)
        
        # -- deduplicate matches --
            unique = {}

            for match in matches:
                unique[match["id"]] = match

            final_matches = list(unique.values())

        # -- get text from matches --
            documents = [ match["metadata"]["text"] for match in final_matches]
            temp  = [ match["metadata"]["file"] for match in final_matches]
            
            if not documents:
                yield {"success": "false", "error": "No relevant documents found" }

            reranked = get_reranking(query=payload.message, documents=documents)

            top_chunks = [ documents[each.index] for each in reranked.results]
            sources = list(set([ temp[each.index] for each in reranked.results]))
            yield json.dumps({"type": "matches", "data": sources}) + "\n"

            
            content  = "\n\n--- next chunk ---\n\n".join(chunk for chunk in top_chunks)

            history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.id.asc()))
            history = history_result.scalars().all()

            messages = [{"role": m.role, "content": m.content} for m in history[-20:]]

            for chunk in ask_llm(history=messages, context=content):
                token = (chunk.choices[0].delta.content)
                if token:
                    full_response+= token
                    yield token
            
            await redis.set(key, full_response,ex=300)
            llm_message = Message(conversation_id=conversation.id, role="assistant", content=full_response,
                                message_metadata={
                                    "user":{
                                    "id": current_user.id
                                    }})
            db.add(llm_message)
            await db.commit()

        return StreamingResponse(stream_llm_response(), media_type="text/plain")
    except Exception as e:
        return not_ok(str(e))
    
@router.delete("/delete/{id}")
async def delete_conversation(id: int, user: CurrentUser, db:Db):
    try:
        result = await db.execute(select(Conversation).where(Conversation.id == id, Conversation.user_id == user.id))
        conversation = result.scalar_one_or_none()

        if not conversation:
            return not_ok("Conversation not found")
        
        await db.delete(conversation)
        res = await db.commit()
        return ok({
            "message": "Successfullly deleted conversation"
        })

    except Exception as e:
        return not_ok("Could not delete conversation. " + str(e))
    
@router.get("/{id}/messages")
async def get_messages(id: int, user: CurrentUser, db:Db):
    try:
        conversation_matches = await db.execute(select(Conversation).where(Conversation.id == id, Conversation.user_id == user.id))
        conversation = conversation_matches.scalar_one_or_none()

        if not conversation:
            return not_ok("No chat found.")
        history_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id.asc()))
        history = history_result.scalars().all()

        messages = [m for m in history]
        return ok(data=messages)

    except Exception as e:
        return not_ok("Could not get messages " + str(e))