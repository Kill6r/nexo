from fastapi import HTTPException
from redis.exceptions import RedisError

SCRIPT_LIMITE = """
local cantidad = redis.call('INCR', KEYS[1])
if cantidad == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {cantidad, redis.call('TTL', KEYS[1])}
"""


async def aplicar_limite(redis, clave: str, limite: int):
    try:
        cantidad, segundos = await redis.eval(SCRIPT_LIMITE, 1, "nexo:limite:" + clave, 60)
    except RedisError as exc:
        raise HTTPException(503, "No se pudo comprobar el limite de solicitudes") from exc
    if cantidad > limite:
        raise HTTPException(
            429, "Demasiadas solicitudes", headers={"Retry-After": str(max(segundos, 1))}
        )
