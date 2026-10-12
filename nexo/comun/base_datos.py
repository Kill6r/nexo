from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def crear_base_datos(url: str):
    motor = create_async_engine(url, pool_pre_ping=True)
    return motor, async_sessionmaker(motor, expire_on_commit=False)
