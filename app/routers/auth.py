from fastapi import APIRouter, Depends, HTTPException
from app.schema import UserCreate, UserLogin, RefreshRequest
from app.db import get_db, AsyncSession
from sqlalchemy import select
from app.models import User
from app.auth import verify_password, hash_password
from app.auth.jwt import create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/auth",tags=["auth"])

# get access token
@router.get("/refresh")
async def refresh_token(payload : RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = decode_token(payload.refresh_token, "refresh")
        access_token = create_access_token(user={"id": user['sub'], "email": user["email"], "name": user["name"]})

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return access_token

# signup
@router.post("/signup")
async def create_account(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    found_user = result.scalar_one_or_none()

    if found_user:
        raise HTTPException(status_code=400, detail="User with email already exists" )

    hashed = hash_password(user_data.password)
    user = User(email=user_data.email, name=user_data.name, password_hash=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    payload = {"id": user.id, "email": user.email, "name":user.name}

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    return {access_token : access_token, refresh_token : refresh_token}

# login
@router.post("/login")
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User does not exists. Create a new account." )
    
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Unauthorized login / Incorrect password" )


    payload = {"id": user.id, "email": user.email, "name":user.name}

    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    return {"access_token" : access_token, "refresh_token" : refresh_token}

