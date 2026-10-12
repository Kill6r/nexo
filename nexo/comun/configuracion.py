from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    url_base_datos: str = Field(
        default="postgresql+asyncpg://nexo:nexo-local-db@localhost:5432/nexo",
        validation_alias="DATABASE_URL",
    )
    url_rabbitmq: str = Field(
        default="amqp://nexo:nexo-local-broker@localhost:5672/",
        validation_alias="RABBITMQ_URL",
    )
    url_redis: str = Field(
        default="redis://:nexo-local-cache@localhost:6379/0",
        validation_alias="REDIS_URL",
    )
    secreto_jwt: str = Field(min_length=32, validation_alias="JWT_SECRET")
    emisor_jwt: str = Field(default="nexo", validation_alias="JWT_ISSUER")
    publico_jwt: str = Field(default="nexo-api", validation_alias="JWT_AUDIENCE")
    minutos_token: int = Field(default=30, ge=1, le=1440, validation_alias="TOKEN_MINUTES")
    limite_por_minuto: int = Field(default=60, ge=1, validation_alias="RATE_LIMIT_PER_MINUTE")
    max_intentos_trabajador: int = Field(
        default=3, ge=1, le=10, validation_alias="WORKER_MAX_ATTEMPTS"
    )
    demora_reintento_ms: int = Field(default=5000, ge=1000, validation_alias="RETRY_DELAY_MS")
    nivel_registro: str = Field(default="INFO", validation_alias="LOG_LEVEL")


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
