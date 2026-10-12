import asyncio
import os
import subprocess
import sys

from sqlalchemy import inspect

from nexo.comun.base_datos import crear_base_datos


async def test_migracion_completa(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'migraciones.db'}"
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "JWT_SECRET": "migration-test-signing-secret-at-least-32-characters",
    }

    def alembic(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    await asyncio.to_thread(alembic, "upgrade", "head")
    await asyncio.to_thread(alembic, "check")
    motor, _ = crear_base_datos(database_url)
    async with motor.connect() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    assert {"users", "events", "outbox"}.issubset(tables)
    await motor.dispose()
    await asyncio.to_thread(alembic, "downgrade", "base")
    motor, _ = crear_base_datos(database_url)
    async with motor.connect() as connection:
        tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    assert "events" not in tables
    await motor.dispose()
