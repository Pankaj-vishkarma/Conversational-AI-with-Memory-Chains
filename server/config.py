import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)


def _to_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    ENV = os.getenv("ENV", "development")
    DEBUG = _to_bool(os.getenv("DEBUG"), default=(ENV == "development"))
    PORT = int(os.getenv("PORT", "5000"))
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")

    SECRET_KEY = os.getenv("SECRET_KEY")

    #  JWT CONFIG
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_EXPIRES", 3600))  # 1 hour

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    # Token Limits
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 4000))
