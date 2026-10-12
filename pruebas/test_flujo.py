import base64
import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from nexo.api.eventos import guardar_evento
from nexo.comun.esquemas import EventoNuevo
from nexo.comun.modelos import Evento, Pendiente, Usuario
from nexo.publicador.principal import publicar_pendiente
from nexo.trabajador.principal import procesar_evento, recibir_mensaje
from pruebas.conftest import autenticar

BODY = {
    "tipo": "github.repositorio.actualizado",
    "origen": "github",
    "datos": {"repositorio": "facebook/react", "estrellas": 240000},
}


async def enviar(cliente, cabeceras, key="event-1", datos=None):
    return await cliente.post(
        "/api/v1/eventos", json=datos or BODY, headers={**cabeceras, "Clave-Idempotencia": key}
    )


async def test_guardar_publicar_procesar_y_repetir(cliente, sesiones, cola):
    cabeceras = await autenticar(cliente)
    respuesta = await enviar(cliente, cabeceras)
    assert respuesta.status_code == 202
    event_id = uuid.UUID(respuesta.json()["id"])
    assert respuesta.json()["estado"] == "pendiente"
    assert cola.publicados == []
    repetido = await enviar(cliente, cabeceras)
    assert repetido.json()["id"] == str(event_id)
    async with sesiones() as sesion:
        assert await sesion.scalar(select(func.count()).select_from(Evento)) == 1
        assert await sesion.scalar(select(func.count()).select_from(Pendiente)) == 1
    assert await publicar_pendiente(sesiones, cola)
    assert cola.publicados == [(event_id, False)]
    assert not await publicar_pendiente(sesiones, cola)
    assert await procesar_evento(sesiones, event_id, 3) == "ack"
    assert await procesar_evento(sesiones, event_id, 3) == "ack"
    result = (await cliente.get(f"/api/v1/eventos/{event_id}", headers=cabeceras)).json()
    assert result["estado"] == "completado"
    assert result["intentos"] == 1
    assert result["resultado"]["popularidad"] == "alta"


async def test_clave_repetida_y_propietario(cliente):
    primero = await autenticar(cliente)
    evento = (await enviar(cliente, primero)).json()
    cambiado = {**BODY, "datos": {"repositorio": "facebook/react", "estrellas": 1}}
    assert (await enviar(cliente, primero, datos=cambiado)).status_code == 409
    segundo = await autenticar(cliente, "other-developer")
    assert (
        await cliente.get(f"/api/v1/eventos/{evento['id']}", headers=segundo)
    ).status_code == 404
    assert (await cliente.get("/api/v1/eventos", headers=segundo)).json()["eventos"] == []
    assert (await enviar(cliente, segundo)).json()["id"] != evento["id"]


async def test_validacion_acceso_y_limites(cliente):
    assert (await enviar(cliente, {})).status_code == 401
    cabeceras = await autenticar(cliente)
    invalido = {**BODY, "datos": {"repositorio": "facebook/react", "estrellas": -1}}
    assert (await enviar(cliente, cabeceras, datos=invalido)).status_code == 422
    assert (await cliente.post("/api/v1/eventos", json=BODY, headers=cabeceras)).status_code == 422
    for i in range(4):
        assert (await enviar(cliente, cabeceras, str(i))).status_code == 202
    limitado = await enviar(cliente, cabeceras, "overflow")
    assert limitado.status_code == 429
    assert int(limitado.headers["Retry-After"]) > 0
    assert (
        await cliente.get("/api/v1/eventos", headers={"Authorization": "Bearer forged-token"})
    ).status_code == 401


async def test_paginas_y_analisis_de_texto(cliente, sesiones):
    cabeceras = await autenticar(cliente)
    text = {"tipo": "texto.analizar", "origen": "demo", "datos": {"texto": "Hola Nexo"}}
    ids = set()
    for i in range(3):
        respuesta = await enviar(cliente, cabeceras, str(i), text)
        ids.add(respuesta.json()["id"])
    page = (await cliente.get("/api/v1/eventos?limite=2", headers=cabeceras)).json()
    next_page = (
        await cliente.get(
            "/api/v1/eventos",
            headers=cabeceras,
            params={"limite": 2, "cursor": page["siguiente_cursor"]},
        )
    ).json()
    assert {evento["id"] for evento in page["eventos"] + next_page["eventos"]} == ids
    assert next_page["siguiente_cursor"] is None
    assert (await cliente.get("/api/v1/eventos?cursor=bad", headers=cabeceras)).status_code == 422
    event_id = uuid.UUID(next(iter(ids)))
    await procesar_evento(sesiones, event_id, 3)
    result = (await cliente.get(f"/api/v1/eventos/{event_id}", headers=cabeceras)).json()[
        "resultado"
    ]
    assert result["palabras"] == 2
    assert result["caracteres"] == 9


async def test_cursores_incorrectos(cliente):
    cabeceras = await autenticar(cliente)
    malformado = [None, {}, [123, {}], ["2026-01-01", str(uuid.uuid4())]]
    for payload in malformado:
        cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        respuesta = await cliente.get(
            "/api/v1/eventos", headers=cabeceras, params={"cursor": cursor}
        )
        assert respuesta.status_code == 422


async def test_pendiente_tras_fallo_de_rabbit(cliente, sesiones, cola):
    cabeceras = await autenticar(cliente)
    await enviar(cliente, cabeceras)
    cola.fallo = True
    with pytest.raises(ConnectionError):
        await publicar_pendiente(sesiones, cola)
    async with sesiones() as sesion:
        item = await sesion.scalar(select(Pendiente))
        assert item.publicado_en is None
    cola.fallo = False
    assert await publicar_pendiente(sesiones, cola)
    assert (await cliente.get("/salud/listo")).status_code == 200
    cola.fallo = True
    assert (await cliente.get("/salud/listo")).status_code == 503


async def test_reintentos_y_error_final(cliente, sesiones):
    cabeceras = await autenticar(cliente)
    event_id = uuid.UUID((await enviar(cliente, cabeceras)).json()["id"])

    def procesador_con_error(evento):
        raise RuntimeError("Private data must not appear in the response")

    assert await procesar_evento(sesiones, event_id, 3, procesador_con_error) == "retry"
    assert await procesar_evento(sesiones, event_id, 3, procesador_con_error) == "retry"
    assert await procesar_evento(sesiones, event_id, 3, procesador_con_error) == "dead"
    assert await procesar_evento(sesiones, event_id, 3, procesador_con_error) == "dead"
    evento = (await cliente.get(f"/api/v1/eventos/{event_id}", headers=cabeceras)).json()
    assert evento["intentos"] == 3
    assert evento["estado"] == "fallido"
    assert evento["error"] == "No se pudo procesar el evento"


class MensajeDePrueba:
    def __init__(self, datos):
        self.body = datos
        self.actions = []
        self.processed = False

    async def ack(self):
        self.actions.append("ack")
        self.processed = True

    async def reject(self, requeue):
        self.actions.append("dead" if not requeue else "requeue")
        self.processed = True

    async def nack(self, requeue):
        self.actions.append("requeue")
        self.processed = True


async def test_mensajes_invalidos_o_perdidos(sesiones, cola):
    malformado = MensajeDePrueba(b"not-json")
    await recibir_mensaje(malformado, sesiones, cola, 3)
    assert malformado.actions == ["dead"]
    desconocido = MensajeDePrueba((f'{{"schema_version":1,"event_id":"{uuid.uuid4()}"}}').encode())
    await recibir_mensaje(desconocido, sesiones, cola, 3)
    assert desconocido.actions == ["dead"]


async def test_guardar_antes_de_confirmar(cliente, sesiones, cola):
    cabeceras = await autenticar(cliente)
    event_id = uuid.UUID((await enviar(cliente, cabeceras)).json()["id"])

    class MensajeConComprobacion(MensajeDePrueba):
        async def ack(self):
            async with sesiones() as sesion:
                evento = await sesion.get(Evento, event_id)
                assert evento.estado == "completed"
            await super().ack()

    mensaje = MensajeConComprobacion((f'{{"event_id":"{event_id}"}}').encode())
    await recibir_mensaje(mensaje, sesiones, cola, 3)
    assert mensaje.actions == ["ack"]


async def test_fallo_al_publicar_reintento(cliente, sesiones, cola, monkeypatch):
    import nexo.trabajador.principal as worker

    cabeceras = await autenticar(cliente)
    event_id = uuid.UUID((await enviar(cliente, cabeceras)).json()["id"])

    async def pedir_reintento(*args):
        return "retry"

    monkeypatch.setattr(worker, "procesar_evento", pedir_reintento)
    mensaje = MensajeDePrueba((f'{{"event_id":"{event_id}"}}').encode())
    cola.fallo = True
    await recibir_mensaje(mensaje, sesiones, cola, 3)
    assert mensaje.actions == ["requeue"]
    cola.fallo = False
    segundo = MensajeDePrueba(mensaje.body)
    await recibir_mensaje(segundo, sesiones, cola, 3)
    assert cola.publicados == [(event_id, True)]
    assert segundo.actions == ["ack"]


async def test_guardado_atomico(sesiones):
    from sqlalchemy import event as sa_event

    async with sesiones() as sesion:
        dueno = Usuario(nombre="dueno", clave_cifrada="prueba")
        sesion.add(dueno)
        await sesion.commit()

    def rechazar_pendiente(mapper, connection, target):
        raise RuntimeError("No se pudo guardar el pendiente")

    sa_event.listen(Pendiente, "before_insert", rechazar_pendiente)
    try:
        with pytest.raises(RuntimeError):
            await guardar_evento(sesiones, dueno.id, EventoNuevo(**BODY), "atomic")
    finally:
        sa_event.remove(Pendiente, "before_insert", rechazar_pendiente)
    async with sesiones() as sesion:
        assert await sesion.scalar(select(func.count()).select_from(Evento)) == 0


async def test_repeticion_con_datos_distintos(cliente, sesiones):
    cabeceras = await autenticar(cliente)
    await enviar(cliente, cabeceras)
    async with sesiones() as sesion:
        dueno = await sesion.scalar(select(Usuario))
    datos = EventoNuevo(**{**BODY, "origen": "different"})
    with pytest.raises(HTTPException) as error:
        await guardar_evento(sesiones, dueno.id, datos, "event-1")
    assert error.value.status_code == 409
