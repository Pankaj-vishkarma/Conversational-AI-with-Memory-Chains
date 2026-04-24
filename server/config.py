import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ENV = os.getenv("ENV", "development")
    DEBUG = ENV == "development"

    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")

    #  JWT CONFIG
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-super-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_EXPIRES", 3600))  # 1 hour

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    # Token Limits
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 4000))
