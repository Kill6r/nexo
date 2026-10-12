import asyncio
import logging

from pydantic import ValidationError
from sqlalchemy import select

from nexo.comun.base_datos import crear_base_datos
from nexo.comun.cola import ColaRabbit
from nexo.comun.configuracion import obtener_configuracion
from nexo.comun.ejecucion import ejecutar_servicio
from nexo.comun.esquemas import MensajeEvento
from nexo.comun.modelos import Evento, ahora_utc
from nexo.comun.registros import configurar_logs
from nexo.trabajador.procesadores import calcular_resultado

registro = logging.getLogger("nexo.trabajador")


async def procesar_evento(sesiones, id_evento, max_intentos, procesador=calcular_resultado):
    async with sesiones() as sesion, sesion.begin():
        evento = await sesion.scalar(select(Evento).where(Evento.id == id_evento).with_for_update())
        if evento is None:
            return "dead"
        if evento.estado == "completed":
            return "ack"
        if evento.estado == "failed":
            return "dead"
        evento.intentos += 1
        try:
            evento.resultado = procesador(evento)
            evento.estado = "completed"
            evento.error = None
            evento.procesado_en = ahora_utc()
            accion = "ack"
        except ValidationError:
            evento.error = "Los datos guardados del evento no son validos"
            evento.estado = "failed"
            evento.procesado_en = ahora_utc()
            accion = "dead"
        except Exception:
            evento.error = "No se pudo procesar el evento"
            evento.estado = "failed" if evento.intentos >= max_intentos else "retrying"
            if evento.estado == "failed":
                evento.procesado_en = ahora_utc()
            accion = "dead" if evento.estado == "failed" else "retry"
        estado, intentos = evento.estado, evento.intentos
    registro.info(
        "evento procesado",
        extra={"id_evento": str(id_evento), "estado": estado, "intentos": intentos},
    )
    return accion


async def recibir_mensaje(mensaje, sesiones, cola, max_intentos):
    try:
        sobre = MensajeEvento.model_validate_json(mensaje.body)
    except ValidationError:
        registro.warning("mensaje incorrecto enviado a la cola de errores")
        await mensaje.reject(requeue=False)
        return
    try:
        accion = await procesar_evento(sesiones, sobre.event_id, max_intentos)
        if accion == "retry":
            await cola.publicar(sobre.event_id, reintento=True)
            await mensaje.ack()
        elif accion == "dead":
            await mensaje.reject(requeue=False)
        else:
            await mensaje.ack()
    except Exception:
        registro.exception(
            "fallo una dependencia; se conserva el mensaje",
            extra={"id_evento": str(sobre.event_id)},
        )
        await asyncio.sleep(1)
        if not mensaje.processed:
            await mensaje.nack(requeue=True)


async def principal():
    configuracion = obtener_configuracion()
    configurar_logs(configuracion.nivel_registro)
    motor, sesiones = crear_base_datos(configuracion.url_base_datos)
    cola = ColaRabbit(configuracion.url_rabbitmq, configuracion.demora_reintento_ms)
    try:
        await cola.conectar()
        async with cola.cola.iterator() as mensajes:
            async for mensaje in mensajes:
                await recibir_mensaje(
                    mensaje, sesiones, cola, configuracion.max_intentos_trabajador
                )
    finally:
        await cola.cerrar()
        await motor.dispose()


if __name__ == "__main__":
    ejecutar_servicio(principal)
