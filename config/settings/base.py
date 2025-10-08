import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(key: str, default: str = "False") -> bool:
    val = os.getenv(key, str(default))
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [x.strip() for x in str(raw).split(",") if x and x.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key")

DEBUG = _env_bool("DEBUG", "True")

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,[::1]",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "debug_toolbar",
    "ninja",
    "corsheaders",
    "api",
    "apps.stock.apps.StockConfig",
    "apps.account",
    "apps.calculate",
    "apps.calendar.apps.CalendarConfig",
    "apps.setting",
    "apps.seapay",
    "apps.logs.apps.LogsConfig",
    "apps.notification.apps.NotificationConfig",
    "core",
]

MIDDLEWARE = [
    "apps.logs.middleware.RequestLoggingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        # Persistent connections - giữ connection trong 60s
        'CONN_MAX_AGE': 60,
        # Health checks - tự động kiểm tra và đóng connections lỗi
        'CONN_HEALTH_CHECKS': True,
        # Connection pool settings
        'OPTIONS': {
            # Limit số connections per process
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',
            "options": "-c search_path=togogonews"
           # aaa
        },
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Authentication Backends (use default)
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Django-Ninja settings
NINJA_PAGINATION_CLASS = 'ninja.pagination.LimitOffsetPagination'
NINJA_PAGINATION_PER_PAGE = 20
NINJA_MAX_PER_PAGE_SIZE = 100
NINJA_PAGINATION_MAX_LIMIT = 100
NINJA_NUM_PROXIES = 0
NINJA_DEFAULT_THROTTLE_RATES = {}
NINJA_FIX_REQUEST_FILES_METHODS = ['PUT', 'PATCH']

# Google OAuth (configure via .env)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL")
APP_ENV = os.getenv("APP_ENV", "local")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_ACCESS_TTL_MIN = int(os.getenv("JWT_ACCESS_TTL_MIN", "60"))
JWT_REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "30"))


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
        "db": {
            "class": "apps.logs.handlers.DatabaseLogHandler",
            "formatter": "plain",
            "level": "INFO",
        },
    },
    "loggers": {
        "app": {
            "handlers": ["db", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["db", "console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
# =========================
# CORS / CSRF
# =========================
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True

# Optional: trusted origins for CSRF (comma-separated)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

CORS_ALLOW_CREDENTIALS = True

# =========================
# CACHE SETTINGS FOR VNSTOCK API
# =========================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vnstock-cache',
        'TIMEOUT': 60 * 60 * 6,  # 6 hours default
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# =========================
# EMAIL SETTINGS
# =========================
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'  # Print to console by default
)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@pynews.com')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', 'True')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
