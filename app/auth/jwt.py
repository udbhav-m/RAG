import app.models
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends, Header
from jose import jwt, JWTError, ExpiredSignatureError
from app.config import settings
from app.schema import UserMe
from app.models import User
from app.db import get_db, AsyncSession
from sqlalchemy import select


def create_token(user: UserMe, token_type: str, expire_delta: timedelta ):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user['id']),       
        "email": user['email'],       
        "name": user['name'],
        "token_type": token_type,
        "iat": int(now.timestamp()),
        "exp" : int((now + expire_delta).timestamp())
    }

    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_access_token(user: UserMe):
    return create_token(user=user, token_type="access", expire_delta=timedelta(minutes=settings.access_token_expire_minutes))

def create_refresh_token(user: UserMe):
    return create_token(user=user, token_type="refresh", expire_delta=timedelta(days=settings.refresh_token_expire_days))

def decode_token(token: str, expected_type: str):
    try:
        payload= jwt.decode(token=token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError:
        raise ValueError("Token expired")
    except JWTError:
        raise ValueError("Invalid token")
    
    if payload.get("token_type") != expected_type:
        raise ValueError(f"Wrong token type: expected {expected_type}")
    
    return payload


async def get_current_user(Authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    try:
        if not Authorization or not Authorization.startswith("Bearer"): 
            raise HTTPException(401, "Missing or malformed token")
    
        token = Authorization.replace("Bearer ", "")
        user_decoded = decode_token(token, expected_type="access")
        result = await db.execute(select(User).where(int(user_decoded['sub']) == User.id))
        user = result.scalar_one_or_none()

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user