import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from nexo.comun.modelos import Usuario

cifrador_claves = PasswordHash.recommended()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/acceso/token")


def crear_token(id_usuario, configuracion):
    ahora = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(id_usuario),
            "iat": ahora,
            "exp": ahora + timedelta(minutes=configuracion.minutos_token),
            "iss": configuracion.emisor_jwt,
            "aud": configuracion.publico_jwt,
        },
        configuracion.secreto_jwt,
        algorithm="HS256",
    )


async def usuario_actual(solicitud: Request, token: str = Depends(oauth2)):
    configuracion = solicitud.app.state.configuracion
    try:
        datos_token = jwt.decode(
            token,
            configuracion.secreto_jwt,
            algorithms=["HS256"],
            issuer=configuracion.emisor_jwt,
            audience=configuracion.publico_jwt,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        id_usuario = uuid.UUID(datos_token["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise HTTPException(
            401, "Token incorrecto o vencido", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    async with solicitud.app.state.sesiones() as sesion:
        usuario = await sesion.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(401, "Token incorrecto o vencido")
    return usuario
