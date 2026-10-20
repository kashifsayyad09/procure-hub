from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class SessionUser(UserOut):
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  (OAuth token type, not a secret)
    expires_in: int
    user: SessionUser


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=1, max_length=128)

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class ErrorBody(BaseModel):
    detail: str | list[str]
