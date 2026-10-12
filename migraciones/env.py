import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from nexo.comun.configuracion import obtener_configuracion
from nexo.comun.modelos import Base

config = context.config
target_metadata = Base.metadata


def configurar(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def conectar():
    motor = create_async_engine(obtener_configuracion().url_base_datos)
    async with motor.connect() as connection:
        await connection.run_sync(configurar)
    await motor.dispose()


if context.is_offline_mode():
    context.configure(
        url=obtener_configuracion().url_base_datos,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(conectar())
