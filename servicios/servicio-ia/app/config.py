"""Configuración del servicio leída de variables de entorno (README D-11, RNF-03)."""

from typing import Annotated

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TextoObligatorio = Annotated[str, Field(min_length=1)]


class ConfiguracionInvalida(Exception):
    """Faltan variables de entorno obligatorias o tienen un valor inválido."""

    def __init__(self, variables: list[str]) -> None:
        self.variables = variables
        super().__init__(
            "Configuración inválida. Revise estas variables de entorno: " + ", ".join(variables)
        )


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    keycloak_issuer: TextoObligatorio
    keycloak_jwks_uri: TextoObligatorio
    keycloak_audience: TextoObligatorio
    keycloak_token_url: TextoObligatorio
    keycloak_client_id: TextoObligatorio
    keycloak_client_secret: SecretStr
    api_gateway_url: TextoObligatorio
    gateway_tiempo_limite_segundos: float = Field(default=5.0, gt=0)
    nivel_log: str = "INFO"

    # spec-trabajos.md 2.2
    google_cloud_project: TextoObligatorio
    rabbitmq_url: SecretStr
    trabajos_cola: TextoObligatorio = "servicio-ia.trabajos"
    trabajos_concurrencia: int = Field(default=2, ge=1, le=20)
    trabajos_consumidor_activo: bool = True
    trabajos_retencion_dias: int = Field(default=30, ge=1)

    # spec-prediccion.md 2.2
    gcs_bucket: TextoObligatorio
    modelos_intervalo_revision_segundos: float = Field(default=60.0, gt=0)

    # spec-vision.md 2.2
    vision_tamanio_maximo_imagen_mb: float = Field(default=10.0, gt=0)
    vision_tamanio_maximo_video_mb: float = Field(default=50.0, gt=0)

    @field_validator("keycloak_client_secret", "rabbitmq_url")
    @classmethod
    def _secreto_no_vacio(cls, valor: SecretStr) -> SecretStr:
        if not valor.get_secret_value().strip():
            raise ValueError("vacío")
        return valor

    @field_validator("api_gateway_url")
    @classmethod
    def _sin_barra_final(cls, valor: str) -> str:
        return valor.rstrip("/")


def cargar_configuracion() -> Configuracion:
    """Lee la configuración; si falla, informa los nombres de las variables sin sus valores."""
    try:
        return Configuracion()
    except ValidationError as error:
        nombres = sorted({str(detalle["loc"][0]).upper() for detalle in error.errors()})
        raise ConfiguracionInvalida(nombres) from None
