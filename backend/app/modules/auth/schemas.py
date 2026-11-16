from typing import Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID


# ----- UserMe Schema -----
class UserMe(BaseModel):
    id: UUID
    email: EmailStr
    role: Optional[str] = None


# ----- SignupRequest Schema -----
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    # full_name: str = None


# ----- SignupResponse Schema -----
class SignupResponse(BaseModel):
    status: str
    message: Optional[str] = None
    user_id: Optional[UUID] = None
