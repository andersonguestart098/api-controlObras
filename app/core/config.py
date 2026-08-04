from functools import lru_cache
from typing import Literal

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    # =========================================================
    # APLICAÇÃO
    # =========================================================

    app_name: str = Field(
        default="Dashboard Gerencial de Obras",
        alias="APP_NAME",
    )

    app_environment: Literal[
        "development",
        "test",
        "production",
    ] = Field(
        default="development",
        alias="APP_ENVIRONMENT",
    )

    app_host: str = Field(
        default="0.0.0.0",
        alias="APP_HOST",
    )

    app_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        alias="APP_PORT",
    )

    cors_origins: str = Field(
        default="http://localhost:5173",
        alias="CORS_ORIGINS",
    )

    # URL do frontend que receberá o token de recuperação.
    # Exemplo:
    # http://localhost:5173/reset-password?token=TOKEN
    frontend_reset_password_url: str = Field(
        default="http://localhost:5173/reset-password",
        alias="FRONTEND_RESET_PASSWORD_URL",
    )

    # =========================================================
    # API KEY INTERNA
    # =========================================================

    api_key: str = Field(
        alias="API_KEY",
    )

    # =========================================================
    # SANKHYA
    # =========================================================

    sankhya_base_url: str = Field(
        alias="SANKHYA_BASE_URL",
    )

    sankhya_auth_url: str = Field(
        alias="SANKHYA_AUTH_URL",
    )

    sankhya_x_token: str = Field(
        alias="SANKHYA_X_TOKEN",
    )

    sankhya_client_id: str = Field(
        alias="SANKHYA_CLIENT_ID",
    )

    sankhya_client_secret: str = Field(
        alias="SANKHYA_CLIENT_SECRET",
    )

    sankhya_timeout_seconds: float = Field(
        default=90.0,
        gt=0,
        alias="SANKHYA_TIMEOUT_SECONDS",
    )

    sankhya_max_connections: int = Field(
        default=10,
        ge=1,
        alias="SANKHYA_MAX_CONNECTIONS",
    )

    sankhya_max_keepalive_connections: int = Field(
        default=5,
        ge=1,
        alias="SANKHYA_MAX_KEEPALIVE_CONNECTIONS",
    )

    sankhya_max_concurrent_queries: int = Field(
        default=3,
        ge=1,
        alias="SANKHYA_MAX_CONCURRENT_QUERIES",
    )

    # =========================================================
    # MONGODB
    # =========================================================

    mongodb_enabled: bool = Field(
        default=False,
        alias="MONGODB_ENABLED",
    )

    # Aceita tanto:
    # MONGODB_URI=...
    #
    # quanto o nome antigo:
    # MONGODB_URL=...
    mongodb_uri: SecretStr = Field(
        default=SecretStr("mongodb://localhost:27017"),
        validation_alias=AliasChoices(
            "MONGODB_URI",
            "MONGODB_URL",
        ),
    )

    mongodb_database: str = Field(
        default="dashboard_obras",
        alias="MONGODB_DATABASE",
    )

    # =========================================================
    # JWT / AUTENTICAÇÃO
    # =========================================================

    jwt_secret_key: SecretStr = Field(
        alias="JWT_SECRET_KEY",
    )

    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
    )

    jwt_access_token_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        alias="JWT_ACCESS_TOKEN_MINUTES",
    )

    jwt_refresh_token_days: int = Field(
        default=7,
        ge=1,
        le=365,
        alias="JWT_REFRESH_TOKEN_DAYS",
    )

    password_reset_token_minutes: int = Field(
        default=20,
        ge=5,
        le=1440,
        alias="PASSWORD_RESET_TOKEN_MINUTES",
    )

    # =========================================================
    # E-MAIL / RECUPERAÇÃO DE SENHA
    # =========================================================

    smtp_enabled: bool = Field(
        default=False,
        alias="SMTP_ENABLED",
    )

    smtp_host: str | None = Field(
        default=None,
        alias="SMTP_HOST",
    )

    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        alias="SMTP_PORT",
    )

    smtp_username: str | None = Field(
        default=None,
        alias="SMTP_USERNAME",
    )

    smtp_password: SecretStr | None = Field(
        default=None,
        alias="SMTP_PASSWORD",
    )

    smtp_from_email: str | None = Field(
        default=None,
        alias="SMTP_FROM_EMAIL",
    )

    smtp_use_tls: bool = Field(
        default=True,
        alias="SMTP_USE_TLS",
    )

    # =========================================================
    # VEXPENSES
    # =========================================================

    vexpenses_base_url: str = Field(
        default="https://api.vexpenses.com/v2",
        alias="VEXPENSES_BASE_URL",
    )

    vexpenses_token: SecretStr = Field(
        alias="VEXPENSES_TOKEN",
    )

    vexpenses_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        alias="VEXPENSES_TIMEOUT_SECONDS",
    )

    vexpenses_max_connections: int = Field(
        default=10,
        ge=1,
        alias="VEXPENSES_MAX_CONNECTIONS",
    )

    vexpenses_max_keepalive_connections: int = Field(
        default=5,
        ge=1,
        alias="VEXPENSES_MAX_KEEPALIVE_CONNECTIONS",
    )

    # =========================================================
    # SCHEDULER
    # =========================================================

    scheduler_enabled: bool = Field(
        default=False,
        alias="SCHEDULER_ENABLED",
    )

    scheduler_timezone: str = Field(
        default="America/Sao_Paulo",
        alias="SCHEDULER_TIMEZONE",
    )

    # =========================================================
    # PROPRIEDADES AUXILIARES
    # =========================================================

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Converte:

        CORS_ORIGINS=http://localhost:5173,https://meu-front.vercel.app

        para:

        [
            "http://localhost:5173",
            "https://meu-front.vercel.app",
        ]
        """

        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def mongodb_url(self) -> str:
        """
        Compatibilidade com códigos antigos que utilizem:

        settings.mongodb_url

        Novos códigos também podem utilizar:

        settings.mongodb_uri.get_secret_value()
        """

        return self.mongodb_uri.get_secret_value()

    @property
    def jwt_access_token_seconds(self) -> int:
        """
        Duração do access token em segundos.
        Útil para enviar expires_in no retorno do login.
        """

        return self.jwt_access_token_minutes * 60

    # =========================================================
    # VALIDAÇÕES
    # =========================================================

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        jwt_secret = self.jwt_secret_key.get_secret_value()

        if len(jwt_secret) < 32:
            raise ValueError(
                "JWT_SECRET_KEY deve possuir pelo menos "
                "32 caracteres."
            )

        if self.smtp_enabled:
            missing_fields: list[str] = []

            if not self.smtp_host:
                missing_fields.append("SMTP_HOST")

            if not self.smtp_from_email:
                missing_fields.append("SMTP_FROM_EMAIL")

            if not self.smtp_username:
                missing_fields.append("SMTP_USERNAME")

            if self.smtp_password is None:
                missing_fields.append("SMTP_PASSWORD")

            if missing_fields:
                raise ValueError(
                    "SMTP_ENABLED=true, mas faltam as "
                    "seguintes configurações: "
                    + ", ".join(missing_fields)
                )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()