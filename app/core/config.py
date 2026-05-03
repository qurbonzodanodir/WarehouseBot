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
    frontend_url: str = "http://localhost:3000"
    extra_frontend_origins: str = "http://127.0.0.1:3000"

    database_url: str = ""

    debug: bool = False

    owner_telegram_id: int = 0

    secret_key: str = "change-me-in-production-use-long-random-string"

    @property
    def SECRET_KEY(self) -> str:
        if (
            not self.debug
            and self.secret_key == "change-me-in-production-use-long-random-string"
        ):
            raise RuntimeError("SECRET_KEY must be set in non-debug environments")
        return self.secret_key

    @property
    def DATABASE_URL(self) -> str:
        if self.database_url:
            return self.database_url
        if self.debug:
            return "postgresql+asyncpg://postgres:postgres@localhost:5432/warehouse_bot"
        raise RuntimeError("DATABASE_URL must be set in non-debug environments")

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host}{self.webhook_path}"

    @property
    def allowed_frontend_origins(self) -> list[str]:
        origins = [self.frontend_url.strip()]
        origins.extend(
            origin.strip()
            for origin in self.extra_frontend_origins.split(",")
            if origin.strip()
        )
        return origins


settings = Settings()
