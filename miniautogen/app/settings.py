from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MiniAutoGenSettings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    default_provider: str = Field("litellm", alias="MINIAUTOGEN_DEFAULT_PROVIDER")
    default_model: str = Field("gpt-4o-mini", alias="MINIAUTOGEN_DEFAULT_MODEL")
    default_timeout_seconds: float = Field(30.0, alias="MINIAUTOGEN_DEFAULT_TIMEOUT_SECONDS")
    default_retry_attempts: int = Field(1, alias="MINIAUTOGEN_DEFAULT_RETRY_ATTEMPTS")
    gateway_base_url: str | None = Field(None, alias="MINIAUTOGEN_GATEWAY_BASE_URL")
    gateway_api_key: str | None = Field(None, alias="MINIAUTOGEN_GATEWAY_API_KEY")
    env: str = Field("development", alias="ENV")

    model_config = SettingsConfigDict(populate_by_name=True, extra="ignore")
