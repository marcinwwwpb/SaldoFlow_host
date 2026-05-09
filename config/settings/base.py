from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = env(name)
    if raw is None:
        return default
    return raw.lower() in {'1', 'true', 'yes', 'on'}


SECRET_KEY = env('DJANGO_SECRET_KEY', 'change-me')
DEBUG = env_bool('DJANGO_DEBUG', False)
DB_ENGINE = (env('DB_ENGINE', 'oracle') or 'oracle').lower()

APP_NAME = env('APP_NAME', 'SaldoFlow')
APP_TAGLINE = env('APP_TAGLINE', 'Dom i firma pod pełną kontrolą.')
APP_MARKETING_LINE = env(
    'APP_MARKETING_LINE',
    'Jedno miejsce do zarządzania budżetem domowym, finansami firmy i automatycznym importem dokumentów.',
)

ALLOWED_HOSTS = [host.strip() for host in (env('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost') or '').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in (env('DJANGO_CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1,http://localhost') or '').split(',') if origin.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'accounts',
    'demon',
    'firma',
    'finanse',
    'paneladmin',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'paneladmin.middleware.CurrentActorMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.app_shell',
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]

LANGUAGE_CODE = 'pl'
TIME_ZONE = 'Europe/Warsaw'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]
LOGIN_URL = '/konto/logowanie/'
LOGIN_REDIRECT_URL = '/moduly/'
LOGOUT_REDIRECT_URL = '/'

EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH = Path(env('EMAIL_FILE_PATH', str(BASE_DIR / 'runtime' / 'emails')))
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'SaldoFlow <no-reply@saldoflow.local>')
EMAIL_HOST = env('EMAIL_HOST', '')
EMAIL_PORT = int(env('EMAIL_PORT', '587') or '587')
EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)

CEIDG_AUTH_TOKEN = env('CEIDG_AUTH_TOKEN', '')
CEIDG_DEMO_MODE = env_bool('CEIDG_DEMO_MODE', DEBUG or not bool(CEIDG_AUTH_TOKEN))
CEIDG_SOAP_URL = env('CEIDG_SOAP_URL', 'https://datastore.ceidg.gov.pl/CEIDG.DataStore/Services/NewDataStoreProvider.svc')

DEMON_STATUS_DIR = BASE_DIR / env('DEMON_STATUS_DIR', 'runtime/daemon_status')
DEMON_SERVICES = {
    'dom': env('DEMON_DOM_SERVICE', 'saldoflow-dom.service'),
    'firma': env('DEMON_FIRMA_SERVICE', 'saldoflow-firma.service'),
}

CONN_MAX_AGE = 60
CONN_HEALTH_CHECKS = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = env('CSRF_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = env('SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')
X_FRAME_OPTIONS = env('X_FRAME_OPTIONS', 'DENY')
SECURE_BROWSER_XSS_FILTER = True


def build_databases() -> dict:
    if DB_ENGINE in {'oracle', 'ora'}:
        oracle_host = env('ORACLE_HOST', '127.0.0.1')
        oracle_port = env('ORACLE_PORT', '1521')
        oracle_service = env('ORACLE_SERVICE_NAME', 'FREEPDB1')
        oracle_dsn = env('ORACLE_DSN', f'{oracle_host}:{oracle_port}/{oracle_service}')
        return {
            'default': {
                'ENGINE': 'django.db.backends.oracle',
                'NAME': oracle_dsn,
                'USER': env('ORACLE_USER', 'SALDOFLOW_APP'),
                'PASSWORD': env('ORACLE_PASSWORD', ''),
                'CONN_MAX_AGE': CONN_MAX_AGE,
                'CONN_HEALTH_CHECKS': True,
            }
        }
    if DB_ENGINE in {'postgres', 'postgresql', 'psql'}:
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': env('POSTGRES_DB', 'saldoflow'),
                'USER': env('POSTGRES_USER', 'saldoflow'),
                'PASSWORD': env('POSTGRES_PASSWORD', ''),
                'HOST': env('POSTGRES_HOST', '127.0.0.1'),
                'PORT': env('POSTGRES_PORT', '5432'),
                'CONN_MAX_AGE': CONN_MAX_AGE,
                'CONN_HEALTH_CHECKS': True,
            }
        }
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / env('SQLITE_NAME', 'db.sqlite3'),
        }
    }


DATABASES = build_databases()


STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
