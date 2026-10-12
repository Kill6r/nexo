import base64
import binascii
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from nexo.comun.esquemas import EventoNuevo
from nexo.comun.modelos import Evento, Pendiente


async def guardar_evento(sesiones, id_usuario: uuid.UUID, datos: EventoNuevo, clave: str) -> Evento:
    huella = datos.calcular_huella()
    async with sesiones() as sesion:
        existente = await sesion.scalar(
            select(Evento).where(
                Evento.id_usuario == id_usuario, Evento.clave_idempotencia == clave
            )
        )
        if existente:
            return comprobar_repeticion(existente, huella)
        evento = Evento(
            id_usuario=id_usuario,
            clave_idempotencia=clave,
            huella=huella,
            tipo=datos.tipo,
            origen=datos.origen,
            datos=datos.datos,
        )
        sesion.add(evento)
        try:
            await sesion.flush()
            sesion.add(Pendiente(id_evento=evento.id))
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            existente = await sesion.scalar(
                select(Evento).where(
                    Evento.id_usuario == id_usuario, Evento.clave_idempotencia == clave
                )
            )
            if existente is None:
                raise
            return comprobar_repeticion(existente, huella)
        return evento


def comprobar_repeticion(evento: Evento, huella: str) -> Evento:
    if evento.huella != huella:
        raise HTTPException(409, "Esta clave ya se uso con otro evento")
    return evento


def crear_cursor(evento: Evento) -> str:
    creado = evento.creado_en
    if creado.tzinfo is None:
        creado = creado.replace(tzinfo=UTC)
    contenido = json.dumps([creado.isoformat(), str(evento.id)]).encode()
    return base64.urlsafe_b64encode(contenido).decode()


async def listar_eventos(sesiones, id_usuario: uuid.UUID, limite: int, cursor: str | None):
    consulta = select(Evento).where(Evento.id_usuario == id_usuario)
    if cursor:
        try:
            decodificado = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if not isinstance(decodificado, list) or len(decodificado) != 2:
                raise ValueError("El cursor tiene un formato incorrecto")
            fecha, id_evento = decodificado
            if not isinstance(fecha, str) or not isinstance(id_evento, str):
                raise ValueError("El cursor tiene datos incorrectos")
            fecha, id_evento = datetime.fromisoformat(fecha), uuid.UUID(id_evento)
            if fecha.tzinfo is None:
                raise ValueError("La fecha del cursor necesita zona horaria")
            fecha = fecha.astimezone(UTC)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise HTTPException(422, "Cursor incorrecto") from exc
        consulta = consulta.where(
            or_(
                Evento.creado_en < fecha,
                and_(Evento.creado_en == fecha, Evento.id < id_evento),
            )
        )
    consulta = consulta.order_by(Evento.creado_en.desc(), Evento.id.desc()).limit(limite + 1)
    async with sesiones() as sesion:
        filas = list((await sesion.scalars(consulta)).all())
    return {
        "eventos": filas[:limite],
        "siguiente_cursor": crear_cursor(filas[limite - 1]) if len(filas) > limite else None,
    }
