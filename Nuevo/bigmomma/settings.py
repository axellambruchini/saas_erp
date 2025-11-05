from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# === Seguridad ===
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = True  # ⚠️ cámbialo a False en producción
ALLOWED_HOSTS = ["*"]  # en producción usa tu dominio/IP

# === Apps instaladas ===
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "inventario",
]

# === Middleware ===
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'inventario.middleware.SetupWizardMiddleware',
]

ROOT_URLCONF = "bigmomma.urls"

# === Templates ===
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # Carpeta global de templates
        "APP_DIRS": True,  # También busca dentro de cada app /templates/
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

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.dev",  # permite cualquier subdominio ngrok
]
WSGI_APPLICATION = "bigmomma.wsgi.application"

# === Base de datos ===
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",  # Usa PostgreSQL en producción
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# === Validación de contraseñas ===
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# === Idioma y zona horaria ===
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# === Archivos estáticos ===
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "bigmomma" / "static",   # donde tú guardas estilos, js, etc.
]
STATIC_ROOT = BASE_DIR / "staticfiles"  # para producción con collectstatic

# === Archivos de usuario (media) ===
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# === Autenticación ===
LOGIN_URL = "login"
# en settings.py
LOGIN_REDIRECT_URL = 'inventario:pagina_precios'  # Después del login, ¿a dónde va?

# Cuando un usuario hace logout, ¿a dónde va?
LOGOUT_REDIRECT_URL = 'inventario:index'

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AZURE_DOCINT_ENDPOINT = "https://recetafactura.cognitiveservices.azure.com/"

# Pega aquí tu "Clave 1"
AZURE_DOCINT_KEY = "whxLFWoGjkPWKEUc96PuE7N09xkTzyGM0pwVa0VvHkZc3cFUw9hCJQQJ99BJACZoyfiXJ3w3AAALACOG0GxE"


# BORRA ESTA LÍNEA de settings.py
AUTH_USER_MODEL = 'inventario.User'