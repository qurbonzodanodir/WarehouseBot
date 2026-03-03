from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    webhook_host: str = ""
    webhook_path: str = "/bot/webhook"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/warehouse_bot"
    )

    debug: bool = False

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host}{self.webhook_path}"


settings = Settings()
