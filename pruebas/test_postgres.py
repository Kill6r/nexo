import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from nexo.api.eventos import guardar_evento
from nexo.comun.base_datos import crear_base_datos
from nexo.comun.esquemas import EventoNuevo
from nexo.comun.modelos import Evento, Pendiente, Usuario
from nexo.trabajador.principal import procesar_evento

pytestmark = pytest.mark.skipif(
    not os.getenv("NEXO_TEST_DATABASE_URL"),
    reason="No migrated PostgreSQL test database configured",
)


@pytest_asyncio.fixture
async def postgres():
    motor, sesiones = crear_base_datos(os.environ["NEXO_TEST_DATABASE_URL"])
    async with sesiones() as sesion:
        dueno = Usuario(nombre="prueba-" + uuid.uuid4().hex, clave_cifrada="prueba")
        sesion.add(dueno)
        await sesion.commit()
    try:
        yield sesiones, dueno.id
    finally:
        async with sesiones() as sesion, sesion.begin():
            events = select(Evento.id).where(Evento.id_usuario == dueno.id)
            await sesion.execute(delete(Pendiente).where(Pendiente.id_evento.in_(events)))
            await sesion.execute(delete(Evento).where(Evento.id_usuario == dueno.id))
            await sesion.execute(delete(Usuario).where(Usuario.id == dueno.id))
        await motor.dispose()


async def test_envios_simultaneos_y_bloqueo(postgres):
    sesiones, owner_id = postgres
    datos = EventoNuevo(tipo="texto.analizar", origen="test", datos={"texto": "Nexo concurrente"})
    events = await asyncio.gather(
        *[guardar_evento(sesiones, owner_id, datos, "same-key") for _ in range(10)]
    )
    assert len({item.id for item in events}) == 1
    event_id = events[0].id
    actions = await asyncio.gather(*[procesar_evento(sesiones, event_id, 3) for _ in range(10)])
    assert actions == ["ack"] * 10
    async with sesiones() as sesion:
        item = await sesion.get(Evento, event_id)
        assert item.intentos == 1
        assert item.estado == "completed"
        assert (
            await sesion.scalar(
                select(func.count()).select_from(Pendiente).where(Pendiente.id_evento == event_id)
            )
            == 1
        )
