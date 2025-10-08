from .base import *

# Use SQLite for tests to avoid external DB dependencies
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Faster password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable validators to speed up
AUTH_PASSWORD_VALIDATORS = []

# Keep DEBUG on for clearer tracebacks in tests
DEBUG = True

# Simplify CORS configuration for tests
CORS_ALLOWED_ORIGINS = []

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
