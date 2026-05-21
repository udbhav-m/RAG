from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str

class UserMe(BaseModel):
    id: int
    email: EmailStr
    name: str

    model_config = {"from_attributes": True}

class RefreshRequest(BaseModel):
    refresh_token: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None