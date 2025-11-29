import os

from ledger import LedgerClient

SECRET_KEY = "django-insecure-example-key-do-not-use-in-production"

DEBUG = True
ALLOWED_HOSTS = ["*"]

ROOT_URLCONF = "your_app.urls"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

LEDGER_CLIENT = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY", "ledger_proj_1_your_api_key"),
    base_url=os.getenv("LEDGER_BASE_URL", "https://ledger-server.jtuta.cloud"),
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "ledger.integrations.django.LedgerMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True
