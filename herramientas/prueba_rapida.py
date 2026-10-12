import argparse
import json
import secrets
import time
import uuid
from pathlib import Path

import httpx


def enviar(cliente):
    usuario = "demo-" + uuid.uuid4().hex[:16]
    clave = secrets.token_urlsafe(24)
    respuesta = cliente.post("/api/v1/acceso/registro", json={"usuario": usuario, "clave": clave})
    respuesta.raise_for_status()
    respuesta = cliente.post("/api/v1/acceso/token", data={"username": usuario, "password": clave})
    respuesta.raise_for_status()

    cabeceras = {
        "Authorization": "Bearer " + respuesta.json()["access_token"],
        "Clave-Idempotencia": "prueba-" + uuid.uuid4().hex,
    }
    datos = {
        "tipo": "texto.analizar",
        "origen": "nexo-demo",
        "datos": {"texto": "Hola Nexo, procesa este evento"},
    }
    respuesta = cliente.post("/api/v1/eventos", headers=cabeceras, json=datos)
    assert respuesta.status_code == 202, respuesta.text
    evento = respuesta.json()
    repetido = cliente.post("/api/v1/eventos", headers=cabeceras, json=datos)
    assert repetido.status_code == 202 and repetido.json()["id"] == evento["id"]
    return {"id_evento": evento["id"], "cabeceras": cabeceras, "estado": evento["estado"]}


def comprobar(cliente, estado):
    plazo = time.monotonic() + 90
    while time.monotonic() < plazo:
        respuesta = cliente.get(
            "/api/v1/eventos/" + estado["id_evento"], headers=estado["cabeceras"]
        )
        respuesta.raise_for_status()
        evento = respuesta.json()
        if evento["estado"] == "completado":
            assert evento["resultado"]["palabras"] == 5
            assert evento["intentos"] == 1
            print("OK: acceso, envio, repeticion y procesamiento")
            print("Evento:", evento["id"])
            return
        assert evento["estado"] != "fallido", evento
        time.sleep(0.5)
    raise TimeoutError("El evento no termino en 90 segundos")


def principal():
    analizador = argparse.ArgumentParser(description="Prueba el procesamiento de eventos de Nexo.")
    analizador.add_argument("--url", default="http://localhost:8000")
    analizador.add_argument(
        "--fase", choices=["completa", "guardar", "comprobar"], default="completa"
    )
    analizador.add_argument("--archivo-estado", type=Path, default=Path(".prueba.json"))
    opciones = analizador.parse_args()

    with httpx.Client(base_url=opciones.url, timeout=10) as cliente:
        if opciones.fase == "comprobar":
            estado = json.loads(opciones.archivo_estado.read_text())
            comprobar(cliente, estado)
            opciones.archivo_estado.unlink()
            return

        estado = enviar(cliente)
        if opciones.fase == "guardar":
            assert estado["estado"] == "pendiente"
            opciones.archivo_estado.write_text(json.dumps(estado))
            print("OK: evento guardado con RabbitMQ y el trabajador detenidos")
        else:
            comprobar(cliente, estado)


if __name__ == "__main__":
    principal()
