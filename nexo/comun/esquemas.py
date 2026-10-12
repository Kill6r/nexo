import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class Registro(BaseModel):
    usuario: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    clave: str = Field(min_length=10, max_length=128)


class DatosRepositorio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repositorio: str = Field(
        min_length=3,
        max_length=200,
        pattern=r"^[\w.-]+/[\w.-]+$",
        validation_alias=AliasChoices("repositorio", "repository"),
    )
    estrellas: int = Field(ge=0, strict=True, validation_alias=AliasChoices("estrellas", "stars"))


class DatosTexto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(
        min_length=1, max_length=10000, validation_alias=AliasChoices("texto", "text")
    )


class EventoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["github.repositorio.actualizado", "texto.analizar"]
    origen: str = Field(min_length=1, max_length=100)
    datos: dict[str, Any]

    @model_validator(mode="after")
    def validar_datos(self):
        esquema = DatosRepositorio if self.tipo == "github.repositorio.actualizado" else DatosTexto
        self.datos = esquema.model_validate(self.datos).model_dump()
        return self

    def calcular_huella(self) -> str:
        contenido = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(contenido.encode()).hexdigest()


class EventoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    origen: str
    datos: dict[str, Any]
    estado: str
    intentos: int
    resultado: dict[str, Any] | None
    error: str | None
    creado_en: datetime
    procesado_en: datetime | None

    @field_validator("estado")
    @classmethod
    def traducir_estado(cls, valor):
        return {
            "pending": "pendiente",
            "retrying": "reintentando",
            "completed": "completado",
            "failed": "fallido",
        }.get(valor, valor)


class PaginaEventos(BaseModel):
    eventos: list[EventoRespuesta]
    siguiente_cursor: str | None


class MensajeEvento(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    event_id: uuid.UUID
