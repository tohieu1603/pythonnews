from django.contrib import admin
from django.urls import path
from api.router import api  
from apps.account.views_oauth_async import oauth_callback

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),  
    path("login/", oauth_callback, name="oauth_callback"),
    path("api/auth/google/callback", oauth_callback, name="google_oauth_callback"),
]
