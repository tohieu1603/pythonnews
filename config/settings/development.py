from .base import *

DEBUG = True

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost,http://127.0.0.1").split(",")

# Database config cho dev (ghi đè nếu cần)
DATABASES["default"]["NAME"] = os.getenv("DB_NAME", "db_dev")
DATABASES["default"]["USER"] = os.getenv("DB_USER", "postgres")
DATABASES["default"]["PASSWORD"] = os.getenv("DB_PASSWORD", "123456789")
DATABASES["default"]["HOST"] = os.getenv("DB_HOST", "localhost")
DATABASES["default"]["PORT"] = os.getenv("DB_PORT", "5432")