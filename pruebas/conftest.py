import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from nexo.api.principal import crear_app
from nexo.comun.base_datos import crear_base_datos
from nexo.comun.configuracion import Configuracion
from nexo.comun.modelos import Base


class RedisFalso:
    def __init__(self):
        self.conteos = {}

    async def eval(self, script, count, key, ttl):
        self.conteos[key] = self.conteos.get(key, 0) + 1
        return self.conteos[key], ttl

    async def ping(self):
        return True


class RabbitFalso:
    def __init__(self):
        self.publicados = []
        self.fallo = False

    async def conectar(self):
        pass

    async def cerrar(self):
        pass

    async def verificar(self):
        if self.fallo:
            raise ConnectionError()

    async def publicar(self, event_id, *, reintento=False):
        if self.fallo:
            raise ConnectionError()
        self.publicados.append((event_id, reintento))


@pytest_asyncio.fixture
async def sesiones(tmp_path):
    motor, sesiones = crear_base_datos(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with motor.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield sesiones
    await motor.dispose()


@pytest.fixture
def cola():
    return RabbitFalso()


@pytest_asyncio.fixture
async def app(sesiones, cola):
    configuracion = Configuracion(
        jwt_secret="test-secret-for-nexo-at-least-32-characters",
        rate_limit_per_minute=4,
        _env_file=None,
    )
    app = crear_app(configuracion, sesiones=sesiones, cliente_redis=RedisFalso(), cola=cola)
    async with app.router.lifespan_context(app):
        yield app


@pytest_asyncio.fixture
async def cliente(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        yield cliente


async def autenticar(cliente, username="developer"):
    respuesta = await cliente.post(
        "/api/v1/acceso/registro", json={"usuario": username, "clave": "test-password-123"}
    )
    assert respuesta.status_code == 201
    respuesta = await cliente.post(
        "/api/v1/acceso/token", data={"username": username, "password": "test-password-123"}
    )
    assert respuesta.status_code == 200
    return {"Authorization": "Bearer " + respuesta.json()["access_token"]}
