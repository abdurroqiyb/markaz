"""Markaz CRM sozlamalari.

Barcha maxfiy va muhitga bog'liq qiymatlar .env fayli yoki muhit
o'zgaruvchilaridan o'qiladi. SECRET_KEY topilmasa avtomatik yaratiladi
va .env fayliga yoziladi.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)


def env_bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def ensure_secret_key():
    """SECRET_KEY: muhitdan, bo'lmasa .env'dan, bo'lmasa yangisini yaratib .env'ga yozadi."""
    key = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY")
    if key:
        return key
    if env_bool("RENDER"):
        print("DIQQAT: SECRET_KEY muhitda yo'q. Render -> Environment ga SECRET_KEY qo'shing, aks holda "
              "har qayta ishga tushishda hamma tizimdan chiqib ketadi.", file=__import__("sys").stderr)
    key = secrets.token_urlsafe(50)
    try:
        with open(ENV_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"\nSECRET_KEY={key}\n")
    except OSError:
        pass  # faqat o'qiladigan tizim: kalit shu jarayon uchun ishlatiladi
    os.environ["SECRET_KEY"] = key
    return key


SECRET_KEY = ensure_secret_key()

# Render'da RENDER=true bo'ladi: DEBUG standart holatda o'chiq.
IS_RENDER = env_bool("RENDER")
DEBUG = env_bool("DEBUG", default=not IS_RENDER)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")
if IS_RENDER and ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "crm",
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
    "crm.branches.BranchMiddleware",
    "crm.middleware.DailyBackupMiddleware",
    "crm.security.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "crm.context_processors.crm",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Ma'lumotlar bazasi:
#  - DATABASE_URL berilsa (masalan bepul Neon PostgreSQL), o'sha ishlatiladi;
#  - aks holda SQLite. Doimiy disk ulansa SQLITE_PATH=/var/data/db.sqlite3 qo'ying.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
            ssl_require=DATABASE_URL.startswith("postgres") and env_bool("DB_SSL_REQUIRE", True),
        )
    }
else:
    SQLITE_PATH = os.environ.get("SQLITE_PATH") or str(BASE_DIR / "db.sqlite3")
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_PATH,
            "OPTIONS": {"timeout": 20},
        }
    }

# Ma'lumotlar doimiy saqlanadimi? Render free tarifida SQLite fayli har deployda o'chadi.
DB_ENGINE = "PostgreSQL" if DATABASE_URL.startswith("postgres") else ("SQLite" if not DATABASE_URL else "Tashqi baza")
DB_PERSISTENT = bool(DATABASE_URL) or bool(os.environ.get("SQLITE_PATH")) or not IS_RENDER
if not DB_PERSISTENT:
    import sys

    print("=" * 70 + "\nDIQQAT: DATABASE_URL berilmagan. Render'da SQLite fayli har deploy va qayta\n"
          "ishga tushishda O'CHIB KETADI. Ma'lumotlar saqlanishi uchun Neon PostgreSQL ulang\n"
          "(README: 'Ma'lumotlar saqlanib qolishi uchun').\n" + "=" * 70, file=sys.stderr)

AUTHENTICATION_BACKENDS = ["crm.security.CaseInsensitiveBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = os.environ.get("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CSRF_FAILURE_VIEW = "crm.errors.csrf_failure"

# Faolsizlikdan keyin avtomatik chiqish (standart 2 soat). Har so'rovda muddat yangilanadi.
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_IDLE_MINUTES", "120")) * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)

# Admin panel manzili (hammaga ma'lum /admin/ emas).
ADMIN_URL = os.environ.get("ADMIN_URL", "boshqaruv-panel").strip("/") + "/"
CSP_ENABLED = env_bool("CSP_ENABLED", True)

# E-pochta (ixtiyoriy): zaxirani pochtaga yuborish uchun.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "crm@localhost")
EMAIL_TIMEOUT = 30

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
