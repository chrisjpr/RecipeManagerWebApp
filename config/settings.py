"""
Django settings for config project – prod-ready, DEBUG-toggleable
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
import django_heroku

# ------------------------------------------------------------
# Base
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Toggle with env: DJANGO_DEBUG=1 for debug; 0/absent for production
DEBUG = os.getenv("DJANGO_DEBUG", "0") in ("1", "true", "True")
# SECRET_KEY required in production
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not DEBUG and not os.getenv("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DEBUG is false")

# Hosts
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# If you deploy on Heroku, optionally add app hostname automatically
HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME")
if HEROKU_APP_NAME:
    ALLOWED_HOSTS.append(f"{HEROKU_APP_NAME}.herokuapp.com")

# Build CSRF trusted origins from ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    # Django expects scheme here
    CSRF_TRUSTED_ORIGINS.append(f"https://{host}")
    if DEBUG:
        CSRF_TRUSTED_ORIGINS.append(f"http://{host}")

AUTH_USER_MODEL = "accounts.CustomUser"

# OpenAI (kept as-is)
OPENAI_KEY = os.getenv("OPENAI_KEY")

# ------------------------------------------------------------
# Static & Media
# ------------------------------------------------------------
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "eu-central-1")
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None

# MEDIA_LOCAL=true -> use local FS; otherwise S3
USE_S3 = os.getenv("MEDIA_LOCAL", "false").lower() not in ("true", "1")

if USE_S3:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_URL = "/media/"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
_static_dir = BASE_DIR / "static"
STATICFILES_DIRS = [str(_static_dir)] if _static_dir.exists() else []

# ------------------------------------------------------------
# Apps & middleware
# ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django_rq",
    "rest_framework",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "accounts",
    "recipes",
    "toolbox",
    "emails",
    "django_user_agents"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------
# Database
# ------------------------------------------------------------
import os, dj_database_url

# Your Supabase connection string
_supabase_url = "postgresql://postgres.nikxdkfhqsywhgfidrjc:ZWldD3rBr33@aws-0-eu-north-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Use DATABASE_URL if provided by environment (Heroku), otherwise Supabase directly
DATABASE_URL = os.getenv("DATABASE_URL", _supabase_url)

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,  # keep SSL enforced for Supabase
    )
}

# ------------------------------------------------------------
# Redis / RQ (single, no duplication)
# ------------------------------------------------------------
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

def _ensure_redis_url_flags(url: str) -> str:
    if not url.startswith("rediss://"):
        return url
    p = urlparse(url)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    q.setdefault("ssl_cert_reqs", "none")
    q.setdefault("ssl_check_hostname", "false")
    return urlunparse(p._replace(query=urlencode(q)))

REDIS_URL = _ensure_redis_url_flags(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))

RQ_QUEUES = {
    "default": {
        "URL": REDIS_URL,
        "DEFAULT_TIMEOUT": 600,
    }
}

if DEBUG:
    try:
        import redis
        redis.Redis.from_url(REDIS_URL).ping()
        print("✅ Redis preflight check successful")
    except Exception as e:
        print("❌ Redis preflight check failed:", e)

# ------------------------------------------------------------
# Passwords / auth
# ------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------
# I18N
# ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# Email
# ------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 465))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "True").lower() in ("true", "1")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# ------------------------------------------------------------
# Security (prod vs dev)
# ------------------------------------------------------------
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_PROXY_SSL_HEADER = None
else:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    # Enable HSTS once you’re sure HTTPS is working end-to-end
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))  # set to 31536000 later
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False

# ------------------------------------------------------------
# Heroku integration
# ------------------------------------------------------------
django_heroku.settings(locals(), databases=False)  # keep our DB config

# ------------------------------------------------------------
# Logging (send errors to console in prod)
# ------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}



