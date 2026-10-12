# Nexo

Nexo recibe eventos y los procesa en segundo plano. La API los guarda en PostgreSQL,
RabbitMQ los entrega a los trabajadores y Redis limita las solicitudes. El publicador
se encarga de enviar a la cola los eventos que ya quedaron guardados.

## Probarlo

Necesitas Docker con Compose. Primero crea el archivo de configuracion:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el valor generado en `JWT_SECRET` dentro de `.env`. Despues inicia los servicios
y ejecuta la prueba rapida:

```powershell
docker compose up --build -d
docker compose exec api python herramientas/prueba_rapida.py
```

En Linux o macOS usa `cp .env.example .env` en lugar de `Copy-Item`. Si ya tienes
un archivo `.env`, no hace falta crearlo otra vez.

La prueba registra un usuario, crea un evento, repite el envio con la misma clave y
espera el resultado. La documentacion interactiva queda en
[localhost:8000/docs](http://localhost:8000/docs). Tambien puedes consultar
[el estado](http://localhost:8000/salud/listo), [las metricas](http://localhost:8000/metricas)
y [RabbitMQ](http://localhost:15672).

## Usar la API

Este ejemplo funciona en PowerShell cuando los servicios estan activos:

```powershell
$url = "http://localhost:8000"
$registro = @{ usuario="demo"; clave="clave-de-prueba-123" } | ConvertTo-Json
Invoke-RestMethod "$url/api/v1/acceso/registro" -Method Post -ContentType "application/json" -Body $registro

$acceso = Invoke-RestMethod "$url/api/v1/acceso/token" -Method Post -Body @{ username="demo"; password="clave-de-prueba-123" }
$cabeceras = @{ Authorization="Bearer $($acceso.access_token)"; "Clave-Idempotencia"="ejemplo-001" }
$datos = @{ tipo="texto.analizar"; origen="ejemplo"; datos=@{ texto="Hola Nexo" } } | ConvertTo-Json -Depth 5

$evento = Invoke-RestMethod "$url/api/v1/eventos" -Method Post -Headers $cabeceras -ContentType "application/json" -Body $datos
Invoke-RestMethod "$url/api/v1/eventos/$($evento.id)" -Headers $cabeceras
```

El inicio de sesion usa `username` y `password` porque sigue el formulario OAuth2.
El resto del ejemplo usa nombres en espanol. Puedes enviar eventos de tipo
`texto.analizar` con `texto`, o `github.repositorio.actualizado` con
`repositorio` y `estrellas`. El segundo tipo procesa los datos que envias; no consulta GitHub.

La API responde 202 cuando guarda el evento. El estado puede ser `pendiente`,
`reintentando`, `completado` o `fallido`. Para listar eventos usa
`GET /api/v1/eventos?limite=20`. Si llega un `siguiente_cursor`, envialo como
`cursor` para pedir la pagina siguiente. Si repites `Clave-Idempotencia` con otros
datos, la API responde 409.

## Desarrollo

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
```

En Linux o macOS cambia `.venv\Scripts\python` por `.venv/bin/python`. La prueba de
concurrencia con PostgreSQL necesita `NEXO_TEST_DATABASE_URL`; GitHub Actions la ejecuta
con una base temporal. Las demas pruebas locales usan SQLite.

Para ver los servicios o iniciar mas trabajadores:

```powershell
docker compose logs -f api publicador trabajador
docker compose up -d --scale trabajador=3
docker compose down
```

`docker compose down` conserva los datos. `docker compose down -v` tambien borra los
volumenes.

## Mas detalles

La [arquitectura](documentacion/arquitectura.md), las
[decisiones](documentacion/decisiones.md), el [plan](documentacion/plan.md)
y la [validacion](documentacion/validacion.md) explican como funciona esta version
y que falta por hacer.
