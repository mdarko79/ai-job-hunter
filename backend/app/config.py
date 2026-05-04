from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = ""  # empty = use provider default
    ai_provider: str = ""   # auto-detect if empty
    ai_base_url: str = ""   # override base URL (for local models)
    frontend_origin: str = "http://localhost:3000"
    database_url: str = "sqlite+aiosqlite:///./job_hunter.db"
    max_applications_per_day_hard_limit: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
