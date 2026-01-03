import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "secret_key")

    MYSQL_HOST = os.getenv("DB_HOST")
    MYSQL_USER = os.getenv("DB_USER")
    MYSQL_PASSWORD = os.getenv("DB_PASSWORD")
    MYSQL_DB = os.getenv("DB_NAME")
    MYSQL_PORT = int(os.getenv("DB_PORT", "3306"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

class DevelopmentConfig(BaseConfig):
    DEBUG = True

class ProductionConfig(BaseConfig):
    DEBUG = False

def get_config():
    env = (os.getenv("APP_ENV") or "production").lower()
    return DevelopmentConfig if env in ("dev", "development") else ProductionConfig
