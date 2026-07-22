from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Dashboard Gerencial de Obras", alias="APP_NAME")
    app_environment: str = Field(default="development", alias="APP_ENVIRONMENT")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    api_key: str = Field(alias="API_KEY")

    sankhya_base_url: str = Field(alias="SANKHYA_BASE_URL")
    sankhya_auth_url: str = Field(alias="SANKHYA_AUTH_URL")
    sankhya_x_token: str = Field(alias="SANKHYA_X_TOKEN")
    sankhya_client_id: str = Field(alias="SANKHYA_CLIENT_ID")
    sankhya_client_secret: str = Field(alias="SANKHYA_CLIENT_SECRET")
    sankhya_timeout_seconds: float = Field(default=90.0, alias="SANKHYA_TIMEOUT_SECONDS")
    sankhya_max_connections: int = Field(default=10, alias="SANKHYA_MAX_CONNECTIONS")
    sankhya_max_keepalive_connections: int = Field(default=5, alias="SANKHYA_MAX_KEEPALIVE_CONNECTIONS")
    sankhya_max_concurrent_queries: int = Field(default=3, alias="SANKHYA_MAX_CONCURRENT_QUERIES")

    mongodb_url: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URL")
    mongodb_database: str = Field(default="dashboard_obras", alias="MONGODB_DATABASE")

    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    scheduler_timezone: str = Field(default="America/Sao_Paulo", alias="SCHEDULER_TIMEZONE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
