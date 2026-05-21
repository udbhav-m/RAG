from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    gemini_api_key: str
    groq_api_key: str
    db_api_key: str
    cohere_api_key: str

    rewrite_llm: str
    chat_llm: str
    embed_llm: str

    db_url: str
    cohere_url: str
    groq_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 3

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()