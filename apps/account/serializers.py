from ninja import Schema
from typing import Optional


class GoogleLoginIn(Schema):
    id_token: str


class AuthTokensOut(Schema):
    access: str
    refresh: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class UserOut(Schema):
    id: int
    email: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class LoginResponse(Schema):
    tokens: AuthTokensOut
    user: UserOut
