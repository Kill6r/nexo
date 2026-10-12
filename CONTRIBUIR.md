# Contribuir

Usa Python 3.12 o 3.13. Las instrucciones para instalar dependencias estan en el README.

Antes de subir un cambio, ejecuta `pytest -q`, `ruff check .` y
`ruff format --check .`. Si cambias la base de datos, crea una migracion Alembic
y comprueba que se pueda aplicar y revertir en una base temporal.

Cada tipo nuevo de evento necesita validar sus datos y definir que pasa si falla
el procesamiento. Si un trabajador llama a un servicio externo, evita que un mensaje
repetido duplique esa accion.

Para actualizar dependencias, instala versiones compatibles en el entorno virtual,
ejecuta `python herramientas/fijar_dependencias.py` y revisa los archivos `.lock`.

No subas `.env`, claves, archivos temporales ni datos personales.
