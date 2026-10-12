import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from redis.asyncio import Redis
from sqlalchemy import text

from nexo.api.acceso import enrutador as enrutador_acceso
from nexo.api.rutas import enrutador as enrutador_eventos
from nexo.comun.base_datos import crear_base_datos
from nexo.comun.cola import ColaRabbit
from nexo.comun.configuracion import obtener_configuracion
from nexo.comun.registros import configurar_logs

registro = logging.getLogger("nexo.api")
SOLICITUDES = Counter(
    "nexo_solicitudes_http_total", "Solicitudes HTTP", ["metodo", "ruta", "estado"]
)
DURACION = Histogram(
    "nexo_duracion_http_seconds", "Duracion de solicitudes HTTP", ["metodo", "ruta"]
)


def crear_app(configuracion=None, *, sesiones=None, cliente_redis=None, cola=None):
    @asynccontextmanager
    async def ciclo_vida(app):
        opciones = configuracion or obtener_configuracion()
        configurar_logs(opciones.nivel_registro)
        app.state.configuracion = opciones
        motor = None
        if sesiones is None:
            motor, app.state.sesiones = crear_base_datos(opciones.url_base_datos)
        else:
            app.state.sesiones = sesiones
        app.state.redis = (
            cliente_redis
            if cliente_redis is not None
            else Redis.from_url(opciones.url_redis, socket_timeout=3, socket_connect_timeout=3)
        )
        app.state.cola = (
            cola
            if cola is not None
            else ColaRabbit(opciones.url_rabbitmq, opciones.demora_reintento_ms)
        )
        try:
            await app.state.cola.conectar()
            yield
        finally:
            await app.state.cola.cerrar()
            if cliente_redis is None:
                await app.state.redis.aclose()
            if motor is not None:
                await motor.dispose()

    app = FastAPI(
        title="Nexo",
        version="0.1.0",
        lifespan=ciclo_vida,
        description="Plataforma de procesamiento de eventos en segundo plano",
    )
    app.include_router(enrutador_acceso)
    app.include_router(enrutador_eventos)

    @app.middleware("http")
    async def registrar_solicitud(solicitud: Request, continuar):
        id_solicitud = str(uuid.uuid4())
        inicio = time.perf_counter()
        respuesta = await continuar(solicitud)
        duracion = time.perf_counter() - inicio

        ruta = getattr(solicitud.scope.get("route"), "path", "sin_ruta")
        SOLICITUDES.labels(solicitud.method, ruta, respuesta.status_code).inc()
        DURACION.labels(solicitud.method, ruta).observe(duracion)
        respuesta.headers["X-Request-ID"] = id_solicitud
        registro.info(
            "solicitud atendida",
            extra={
                "id_solicitud": id_solicitud,
                "estado": respuesta.status_code,
                "duracion_ms": round(duracion * 1000, 2),
            },
        )
        return respuesta

    @app.get("/salud/vivo", tags=["Estado del servicio"])
    async def vivo():
        return {"estado": "bien"}

    @app.get("/salud/listo", tags=["Estado del servicio"])
    async def listo(solicitud: Request):
        try:
            async with solicitud.app.state.sesiones() as sesion:
                await sesion.execute(text("SELECT 1"))
            await solicitud.app.state.redis.ping()
            await solicitud.app.state.cola.verificar()
        except Exception as exc:
            raise HTTPException(503, "Hay servicios que no estan disponibles") from exc
        return {"estado": "listo"}

    @app.get("/metricas", include_in_schema=False)
    async def metricas():
        return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return app


app = crear_app()
