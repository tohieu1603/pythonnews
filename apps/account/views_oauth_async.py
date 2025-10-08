from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
import asyncio
import aiohttp
import jwt
from datetime import datetime, timedelta, timezone
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from urllib.parse import urlencode

User = get_user_model()


async def oauth_callback_async(request):
    """Google OAuth redirect handler"""
    
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "Missing authorization code"}, status=400)

    try:
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=3, connect=1)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
    
            token_data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            }
            
            async with session.post(
                "https://oauth2.googleapis.com/token",
                data=token_data
            ) as token_response:
                if token_response.status != 200:
                    return JsonResponse({"error": "Failed to get access token"}, status=400)
                
                token_json = await token_response.json()
                access_token = token_json.get("access_token")
                
                if not access_token:
                    return JsonResponse({"error": "No access token received"}, status=400)

            async with session.get(
                f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}"
            ) as user_response:
                if user_response.status != 200:
                    return JsonResponse({"error": "Failed to get user info"}, status=400)
                
                google_user = await user_response.json()

        User = get_user_model()
        
        user, _ = await sync_to_async(User.objects.get_or_create)(
            email=google_user["email"],
            defaults={
                "first_name": google_user.get("given_name", ""),
                "last_name": google_user.get("family_name", ""),
                "is_active": True
            }
        )
        
        access_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24)
        }
        
        refresh_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "type": "refresh", 
            "exp": datetime.now(timezone.utc) + timedelta(days=7)
        }
        
        access_token = jwt.encode(
            access_payload, 
            settings.JWT_SECRET, 
            algorithm="HS256"
        )
        
        refresh_token = jwt.encode(
            refresh_payload,
            settings.JWT_SECRET,
            algorithm="HS256"
        )

        frontend_base = (
            request.GET.get("redirect")
            or request.GET.get("next")
            or getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        )

        response = HttpResponseRedirect(frontend_base)

        access_max_age = 24 * 60 * 60 
        refresh_max_age = 7 * 24 * 60 * 60 
        secure_flag = not getattr(settings, "DEBUG", True)

        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=access_max_age,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=refresh_max_age,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
            path="/",
        )

        return response
        
    except asyncio.TimeoutError:
        return JsonResponse({"error": "Request timeout - try again"}, status=408)
    except Exception as e:
        return JsonResponse({"error": f"Login failed: {str(e)}"}, status=500)


def oauth_callback(request):
    """Sync wrapper for async OAuth callback"""
    return asyncio.run(oauth_callback_async(request))
