from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from nexo.api.limites import aplicar_limite
from nexo.api.seguridad import cifrador_claves, crear_token
from nexo.comun.esquemas import Registro
from nexo.comun.modelos import Usuario

enrutador = APIRouter(prefix="/api/v1/acceso", tags=["Acceso"])


async def limitar_intentos(solicitud: Request):
    host = solicitud.client.host if solicitud.client else "desconocido"
    await aplicar_limite(solicitud.app.state.redis, f"auth:{host}", 20)


@enrutador.post("/registro", status_code=201, dependencies=[Depends(limitar_intentos)])
async def registrar(datos: Registro, solicitud: Request):
    clave_cifrada = await run_in_threadpool(cifrador_claves.hash, datos.clave)
    async with solicitud.app.state.sesiones() as sesion:
        usuario = Usuario(nombre=datos.usuario, clave_cifrada=clave_cifrada)
        sesion.add(usuario)
        try:
            await sesion.commit()
        except IntegrityError as exc:
            await sesion.rollback()
            raise HTTPException(409, "Ese usuario ya existe") from exc
    return {"id": usuario.id, "usuario": usuario.nombre}


@enrutador.post("/token", dependencies=[Depends(limitar_intentos)])
async def iniciar_sesion(solicitud: Request, form: OAuth2PasswordRequestForm = Depends()):
    if len(form.password) > 128 or len(form.username) > 64:
        raise HTTPException(401, "Usuario o clave incorrectos")

    async with solicitud.app.state.sesiones() as sesion:
        usuario = await sesion.scalar(select(Usuario).where(Usuario.nombre == form.username))

    if usuario is None:
        await run_in_threadpool(cifrador_claves.hash, form.password)
        valido = False
    else:
        valido = await run_in_threadpool(
            cifrador_claves.verify, form.password, usuario.clave_cifrada
        )

    if not valido:
        raise HTTPException(
            401, "Usuario o clave incorrectos", headers={"WWW-Authenticate": "Bearer"}
        )
    return {
        "access_token": crear_token(usuario.id, solicitud.app.state.configuracion),
        "token_type": "bearer",
    }
