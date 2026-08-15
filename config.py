from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://admin:admin@localhost:5432/trading_journal"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
