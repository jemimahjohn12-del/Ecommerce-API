from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    test_database_url: str | None = None  # only needed to run the tests

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()