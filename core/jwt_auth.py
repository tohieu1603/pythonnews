import datetime as dt
from typing import Any, Dict, Tuple

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer

User = get_user_model()


class JWTAuth(HttpBearer):
    """Authenticate requests using a bearer JWT token."""

    def authenticate(self, request, token: str):  
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except Exception:
            return None
        user_id = payload.get("user_id") or payload.get("sub")
        if not user_id:
            return None
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


def cookie_or_bearer_jwt_auth(request):
    """Authenticate via Authorization header or access_token cookie."""
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    else:
        token = request.COOKIES.get("access_token")

    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        return None
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        return None
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def create_tokens(user_id: int, email: str | None = None) -> Tuple[str, str, int, int]:
    access_ttl = int(getattr(settings, "JWT_ACCESS_TTL_MIN", 60))
    refresh_ttl_days = int(getattr(settings, "JWT_REFRESH_TTL_DAYS", 30))

    now = _now()
    access_exp = now + dt.timedelta(minutes=access_ttl)
    refresh_exp = now + dt.timedelta(days=refresh_ttl_days)

    base_claims: Dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
    }
    if email:
        base_claims["email"] = email

    access_claims = {**base_claims, "type": "access", "exp": int(access_exp.timestamp())}
    refresh_claims = {**base_claims, "type": "refresh", "exp": int(refresh_exp.timestamp())}

    secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
    alg = getattr(settings, "JWT_ALGORITHM", "HS256")

    access = jwt.encode(access_claims, secret, algorithm=alg)
    refresh = jwt.encode(refresh_claims, secret, algorithm=alg)
    return access, refresh, access_ttl * 60, refresh_ttl_days * 24 * 3600


def decode_token(token: str) -> Dict[str, Any]:
    secret = getattr(settings, "JWT_SECRET", settings.SECRET_KEY)
    alg = getattr(settings, "JWT_ALGORITHM", "HS256")
    return jwt.decode(token, secret, algorithms=[alg])


def create_jwt_token(user, *, include_refresh: bool = False):
    """Return a signed JWT access token for the given user."""
    email = getattr(user, "email", None)
    access, refresh, _, _ = create_tokens(user_id=user.id, email=email)
    return (access, refresh) if include_refresh else access
