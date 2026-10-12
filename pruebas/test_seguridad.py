import uuid
from datetime import UTC, datetime, timedelta

import jwt
from redis.exceptions import ConnectionError as RedisConnectionError

from nexo.api.seguridad import crear_token
from pruebas.conftest import autenticar


async def test_tokens_invalidos(cliente, app):
    configuracion = app.state.configuracion
    cabeceras = await autenticar(cliente)
    valido = cabeceras["Authorization"].removeprefix("Bearer ")
    datos_token = jwt.decode(
        valido,
        configuracion.secreto_jwt,
        algorithms=["HS256"],
        issuer=configuracion.emisor_jwt,
        audience=configuracion.publico_jwt,
    )
    vencido = jwt.encode(
        {**datos_token, "exp": datetime.now(UTC) - timedelta(seconds=1)},
        configuracion.secreto_jwt,
        algorithm="HS256",
    )
    destino_incorrecto = jwt.encode(
        {**datos_token, "aud": "other-service"}, configuracion.secreto_jwt, algorithm="HS256"
    )
    usuario_inexistente = crear_token(uuid.uuid4(), configuracion)
    for token in [vencido, destino_incorrecto, usuario_inexistente]:
        assert (
            await cliente.get("/api/v1/eventos", headers={"Authorization": "Bearer " + token})
        ).status_code == 401


async def test_acceso_fallido_y_usuario_repetido(cliente):
    await autenticar(cliente)
    duplicate = await cliente.post(
        "/api/v1/acceso/registro", json={"usuario": "developer", "clave": "another-password"}
    )
    assert duplicate.status_code == 409
    for username in ["developer", "does-not-exist"]:
        respuesta = await cliente.post(
            "/api/v1/acceso/token", data={"username": username, "password": "wrong-password"}
        )
        assert respuesta.status_code == 401
        assert respuesta.json()["detail"] == "Usuario o clave incorrectos"


async def test_fallo_de_redis_rechaza_evento(cliente, app, sesiones):
    from sqlalchemy import func, select

    from nexo.comun.modelos import Evento

    cabeceras = await autenticar(cliente)

    class RedisSinConexion:
        async def eval(self, *args):
            raise RedisConnectionError("offline")

    app.state.redis = RedisSinConexion()
    respuesta = await cliente.post(
        "/api/v1/eventos",
        headers={**cabeceras, "Clave-Idempotencia": "redis-outage"},
        json={"tipo": "texto.analizar", "origen": "test", "datos": {"texto": "hello"}},
    )
    assert respuesta.status_code == 503
    async with sesiones() as sesion:
        assert await sesion.scalar(select(func.count()).select_from(Evento)) == 0
