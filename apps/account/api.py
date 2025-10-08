from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import jwt
import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from ninja import Router
from ninja.responses import Response
from pydantic import BaseModel, Field, validator

from core.jwt_auth import cookie_or_bearer_jwt_auth
from .models import SocialAccount

User = get_user_model()

router = Router(tags=["auth"])


AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
DEFAULT_SCOPES = "openid email profile"
HTTP_TIMEOUT = 10 



class GoogleOAuthError(Exception):
    """Base exception for Google OAuth flow."""


class GoogleTokenExchangeError(GoogleOAuthError):
    """Raised when exchanging code for tokens fails."""


class GoogleIdTokenError(GoogleOAuthError):
    """Raised when verifying Google ID token fails."""



@dataclass
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str = DEFAULT_SCOPES
    prompt: str = "consent"
    access_type: str = "offline"
    include_granted_scopes: str = "true"

    @property
    def audience_list(self) -> List[str]:
        return [c.strip() for c in self.client_id.split(",") if c.strip()]


@dataclass
class GoogleProfile:
    sub: str
    email: Optional[str]
    name: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    picture: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoogleProfile":
        sub = data.get("sub") or data.get("id")
        if not sub:
            raise GoogleOAuthError("Google profile missing 'sub' identifier")
        return cls(
            sub=str(sub),
            email=data.get("email"),
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
        )


def _require_setting(name: str) -> str:
    value = getattr(settings, name, None)
    if not value:
        raise GoogleOAuthError(f"Missing Google OAuth setting: {name}")
    return value


def _load_oauth_config() -> GoogleOAuthConfig:
    return GoogleOAuthConfig(
        client_id=_require_setting("GOOGLE_CLIENT_ID"),
        client_secret=_require_setting("GOOGLE_CLIENT_SECRET"),
        redirect_uri=_require_setting("GOOGLE_REDIRECT_URI"),
        scopes=getattr(settings, "GOOGLE_SCOPES", DEFAULT_SCOPES) or DEFAULT_SCOPES,
    )


def _http_get(url: str, *, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    response = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if response.status_code != 200:
        raise GoogleOAuthError(f"Google API GET {url} failed: {response.status_code}")
    return response.json()


def _http_post(url: str, *, data: Dict[str, Any]) -> Dict[str, Any]:
    import json
    print(f"[DEBUG] POST {url}")
    print(f"[DEBUG] Data: {json.dumps(data, indent=2)}")
    response = requests.post(url, data=data, timeout=HTTP_TIMEOUT)
    print(f"[DEBUG] Response status: {response.status_code}")
    print(f"[DEBUG] Response text: {response.text[:500]}")
    if response.status_code != 200:
        if response.headers.get("content-type", "").startswith("application/json"):
            error_data = response.json()
            error_msg = error_data.get("error_description") or error_data.get("error") or str(error_data)
        else:
            error_msg = response.text
        raise GoogleTokenExchangeError(f"Google token endpoint error: {error_msg}")
    return response.json()


def _create_or_link_user(profile: GoogleProfile) -> User:
    linked = SocialAccount.objects.select_related("user").filter(
        provider=SocialAccount.PROVIDER_GOOGLE,
        sub=profile.sub,
    ).first()
    if linked:
        user = linked.user
    else:
        user = None
        if profile.email:
            user = User.objects.filter(email__iexact=profile.email).first()
        if not user:
            username = profile.email or f"google_{profile.sub}"
            user = User.objects.create_user(username=username, email=profile.email)
        SocialAccount.objects.update_or_create(
            provider=SocialAccount.PROVIDER_GOOGLE,
            sub=profile.sub,
            defaults={"user": user, "email": profile.email},
        )

    changed = False
    if hasattr(user, "first_name") and profile.given_name and not user.first_name:
        user.first_name = profile.given_name
        changed = True
    if hasattr(user, "last_name") and profile.family_name and not user.last_name:
        user.last_name = profile.family_name
        changed = True
    if changed:
        user.save(update_fields=["first_name", "last_name"])
    return user


def _issue_jwt_pair(user: User) -> Dict[str, str]:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    access_payload = {
        "user_id": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
        "type": "access",
    }
    refresh_payload = {
        "user_id": user.id,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        "type": "refresh",
    }

    access_token = jwt.encode(access_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"access_token": access_token, "refresh_token": refresh_token}


def _serialize_user(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": getattr(user, "email", None),
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
    }


def _build_error(message: str, status: int = 400, *, detail: Optional[Any] = None) -> Response:
    payload: Dict[str, Any] = {"error": message}
    if detail is not None:
        payload["detail"] = detail
    return Response(payload, status=status)


# --- Schemas --------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class GoogleLoginRequest(BaseModel):
    code: str = Field(..., description="Authorization code returned by Google")
    redirect_uri: Optional[str] = Field(None, description="Override redirect_uri if needed")
    code_verifier: Optional[str] = Field(None, description="PKCE code_verifier when using PKCE")


class GoogleIdTokenRequest(BaseModel):
    id_token: str = Field(..., description="ID token issued by Google")

    @validator("id_token")
    def _trim(cls, value: str) -> str:
        return value.strip()


class UserPayload(BaseModel):
    id: int
    email: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserPayload


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str


class MessageResponse(BaseModel):
    message: str


class GoogleOAuthService:
    def __init__(self, config: GoogleOAuthConfig):
        self.config = config

    def build_authorization_url(self, *, state: Optional[str] = None, include_prompt: bool = True) -> str:
        params: Dict[str, Any] = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scopes,
            "access_type": self.config.access_type,
            "include_granted_scopes": self.config.include_granted_scopes,
        }
        if include_prompt and self.config.prompt:
            params["prompt"] = self.config.prompt
        if state:
            params["state"] = state
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange_code(self, request: GoogleLoginRequest) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "code": request.code.strip(),
            "client_id": self.config.client_id.strip(),
            "client_secret": self.config.client_secret.strip(),
            "redirect_uri": (request.redirect_uri or self.config.redirect_uri).strip(),
            "grant_type": "authorization_code",
        }
        if request.code_verifier:
            data["code_verifier"] = request.code_verifier.strip()
        return _http_post(TOKEN_ENDPOINT, data=data)

    def fetch_profile_from_access_token(self, access_token: str) -> GoogleProfile:
        payload = _http_get(USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"})
        return GoogleProfile.from_dict(payload)

    def verify_id_token(self, id_token: str) -> GoogleProfile:
        audiences = self.config.audience_list
        if not audiences:
            raise GoogleIdTokenError("Invalid GOOGLE_CLIENT_ID configuration")

        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            req = google_requests.Request()
            last_error: Optional[Exception] = None
            payload: Optional[Dict[str, Any]] = None
            for aud in audiences:
                try:
                    payload = google_id_token.verify_oauth2_token(id_token, req, aud)
                    if payload:
                        break
                except Exception as exc:  # noqa: PERF203
                    last_error = exc
                    continue
            if not payload:
                raise GoogleIdTokenError(str(last_error) if last_error else "Unable to verify ID token")
            if payload.get("aud") not in audiences:
                raise GoogleIdTokenError("ID token audience is not allowed")
            return GoogleProfile.from_dict(payload)
        except ImportError:
            token_info = _http_get(TOKENINFO_ENDPOINT, params={"id_token": id_token})
            if token_info.get("aud") not in audiences:
                raise GoogleIdTokenError("ID token audience is not allowed")
            return GoogleProfile.from_dict(token_info)


# --- Endpoint Implementations ---------------------------------------------------


def _google_service() -> GoogleOAuthService:
    return GoogleOAuthService(_load_oauth_config())


@router.get("/google/auth-url", response=GoogleAuthUrlResponse)
def google_auth_url(request, state: Optional[str] = None):
    try:
        service = _google_service()
        url = service.build_authorization_url(state=state)
        return GoogleAuthUrlResponse(auth_url=url)
    except GoogleOAuthError as exc:
        return _build_error(str(exc), status=500)


@router.post("/google/login")
def google_login(request, payload: GoogleLoginRequest):
    try:
        service = _google_service()
        token_payload = service.exchange_code(payload)
        access_token = token_payload.get("access_token")
        if not access_token:
            raise GoogleTokenExchangeError("Google did not return an access_token")

        profile = service.fetch_profile_from_access_token(access_token)
        user = _create_or_link_user(profile)
        tokens = _issue_jwt_pair(user)
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserPayload(**_serialize_user(user)),
        )
    except GoogleOAuthError as exc:
        return _build_error("Google sign-in failed", status=400, detail=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        error_detail = str(exc) if exc else "Unknown error"
        return _build_error("Google sign-in failed", status=400, detail=error_detail)


@router.post("/google/login-id-token", response=TokenResponse)
def google_login_id_token(request, payload: GoogleIdTokenRequest):
    try:
        service = _google_service()
        profile = service.verify_id_token(payload.id_token)
        user = _create_or_link_user(profile)
        tokens = _issue_jwt_pair(user)
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserPayload(**_serialize_user(user)),
        )
    except GoogleIdTokenError as exc:
        return _build_error(str(exc), status=400)
    except GoogleOAuthError as exc:
        return _build_error(str(exc), status=400)
    except Exception as exc:
        return _build_error("Google ID token sign-in failed", status=400, detail=str(exc))


@router.post("/login", response=TokenResponse)
def login(request, payload: LoginRequest):
    user = authenticate(username=payload.email, password=payload.password)
    if not user:
        return _build_error("Invalid email or password", status=401)
    if not user.is_active:
        return _build_error("Account has been disabled", status=401)

    tokens = _issue_jwt_pair(user)
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserPayload(**_serialize_user(user)),
    )


@router.get("/profile", auth=cookie_or_bearer_jwt_auth)
def get_profile(request):
    try:
        return _serialize_user(request.auth)
    except Exception as exc:
        return _build_error("Failed to load user profile", status=400, detail=str(exc))
