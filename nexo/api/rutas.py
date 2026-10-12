import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select

from nexo.api.eventos import guardar_evento, listar_eventos
from nexo.api.limites import aplicar_limite
from nexo.api.seguridad import usuario_actual
from nexo.comun.esquemas import EventoNuevo, EventoRespuesta, PaginaEventos
from nexo.comun.modelos import Evento, Usuario

enrutador = APIRouter(prefix="/api/v1/eventos", tags=["Eventos"])


@enrutador.post("", response_model=EventoRespuesta, status_code=202)
async def enviar_evento(
    datos: EventoNuevo,
    solicitud: Request,
    usuario: Usuario = Depends(usuario_actual),
    clave_idempotencia: str = Header(min_length=1, max_length=128, alias="Clave-Idempotencia"),
):
    await aplicar_limite(
        solicitud.app.state.redis,
        f"ingest:{usuario.id}",
        solicitud.app.state.configuracion.limite_por_minuto,
    )
    return await guardar_evento(solicitud.app.state.sesiones, usuario.id, datos, clave_idempotencia)


@enrutador.get("", response_model=PaginaEventos)
async def consultar_eventos(
    solicitud: Request,
    usuario: Usuario = Depends(usuario_actual),
    limite: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
):
    return await listar_eventos(solicitud.app.state.sesiones, usuario.id, limite, cursor)


@enrutador.get("/{id_evento}", response_model=EventoRespuesta)
async def consultar_evento(
    id_evento: uuid.UUID, solicitud: Request, usuario: Usuario = Depends(usuario_actual)
):
    async with solicitud.app.state.sesiones() as sesion:
        item = await sesion.scalar(
            select(Evento).where(Evento.id == id_evento, Evento.id_usuario == usuario.id)
        )
    if item is None:
        raise HTTPException(404, "Evento no encontrado")
    return item
