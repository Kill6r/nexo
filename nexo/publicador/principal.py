import asyncio
import logging

from sqlalchemy import select

from nexo.comun.base_datos import crear_base_datos
from nexo.comun.cola import ColaRabbit
from nexo.comun.configuracion import obtener_configuracion
from nexo.comun.ejecucion import ejecutar_servicio
from nexo.comun.modelos import Pendiente, ahora_utc
from nexo.comun.registros import configurar_logs

registro = logging.getLogger("nexo.publicador")


async def publicar_pendiente(sesiones, cola):
    async with sesiones() as sesion, sesion.begin():
        pendiente = await sesion.scalar(
            select(Pendiente)
            .where(Pendiente.publicado_en.is_(None))
            .order_by(Pendiente.creado_en)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if pendiente is None:
            return False
        await cola.publicar(pendiente.id_evento)
        pendiente.publicado_en = ahora_utc()
        id_evento = str(pendiente.id_evento)
    registro.info("evento publicado", extra={"id_evento": id_evento})
    return True


async def principal():
    configuracion = obtener_configuracion()
    configurar_logs(configuracion.nivel_registro)
    motor, sesiones = crear_base_datos(configuracion.url_base_datos)
    cola = ColaRabbit(configuracion.url_rabbitmq, configuracion.demora_reintento_ms)
    try:
        await cola.conectar()
        while True:
            try:
                if not await publicar_pendiente(sesiones, cola):
                    await asyncio.sleep(0.5)
            except Exception:
                registro.exception("fallo la publicacion; el evento sigue pendiente")
                await asyncio.sleep(2)
    finally:
        await cola.cerrar()
        await motor.dispose()


if __name__ == "__main__":
    ejecutar_servicio(principal)
