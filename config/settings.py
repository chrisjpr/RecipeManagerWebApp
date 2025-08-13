"""
Django settings for config project – dev/prod safe
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import django_heroku
import ssl
# ------------------------------------------------------------
# Base
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / '.env', override=True)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]

AUTH_USER_MODEL = "accounts.CustomUser"

# OPEN AI KEY
OPENAI_KEY = os.getenv("OPENAI_KEY")

# ------------------------------------------------------------
# Static & media
# ------------------------------------------------------------
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'eu-central-1'
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None

USE_S3 = os.getenv("MEDIA_LOCAL", "False").lower() not in ("true", "1")

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
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    MEDIA_URL = "/media/"

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# Only include local static dir if it actually exists (avoids Heroku warning)
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
    "emails",
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
# RQ / Redis (background jobs)
# ------------------------------------------------------------
# Use Heroku's REDIS_URL when present; fall back to local dev Redis.
REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
print("[SETTINGS - RQ DEBUG] REDIS_URL:", REDIS_URL)

RQ_QUEUES = {
    "default": {
        "URL": REDIS_URL,
        "DEFAULT_TIMEOUT": 600,
        "OPTIONS": {"ssl_cert_reqs": ssl.CERT_NONE},  # disables cert verification
    }
}

# ------------------------------------------------------------
# Database
# ------------------------------------------------------------
# Use DATABASE_URL when set; otherwise fall back to local dev DB
_default_local = "postgres://recipe_user:2411@127.0.0.1:5432/recipe_db"
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", _default_local),
        conn_max_age=600,
        ssl_require=not DEBUG,   # require SSL only in production
    )
}
print("[SETTINGS - DATABASE DEBUG] Active DATABASE_URL:", os.getenv("DATABASE_URL", _default_local))

# ------------------------------------------------------------
# Password validation
# ------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Avoid auto-field warning from django_rq models
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
# Security: split dev vs prod
# ------------------------------------------------------------
# Build CSRF_TRUSTED_ORIGINS from ALLOWED_HOSTS so both http/https work in dev.
_csrf_hosts = [h for h in ALLOWED_HOSTS if h]
CSRF_TRUSTED_ORIGINS = []
for host in _csrf_hosts:
    if DEBUG:
        CSRF_TRUSTED_ORIGINS.append(f"http://{host}")
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")
    else:
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

if DEBUG:
    # Local dev: do NOT force HTTPS, do NOT mark cookies secure-only
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_PROXY_SSL_HEADER = None
else:
    # Production (e.g., Heroku): enforce HTTPS & secure cookies
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ------------------------------------------------------------
# Heroku integration (kept, but safe for dev)
# ------------------------------------------------------------
django_heroku.settings(locals(), databases=False)

# Pre-warm Redis connection to avoid SSL errors on first request
import ssl
import redis

try:
    if REDIS_URL.startswith("rediss://"):
        r = redis.Redis.from_url(REDIS_URL, ssl_cert_reqs=ssl.CERT_NONE)
        r.ping()
        print("✅ Redis preflight check (web dyno) successful")
except Exception as e:
    print("❌ Redis preflight check failed:", e)
