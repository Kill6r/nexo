# Validacion

Comprobado el 12 de octubre de 2026 en Windows con Python 3.13.15:

- 16 pruebas pasaron y una prueba de PostgreSQL se omitio en local.
- Ruff no encontro problemas de estilo.
- Alembic pudo aplicar, comparar y revertir las migraciones con SQLite.
- Las dependencias instaladas no mostraron conflictos.

Las pruebas cubren acceso, tokens vencidos, aislamiento entre usuarios, validacion
de eventos, limites, paginacion, claves repetidas, fallos de publicacion, reintentos
y el orden entre guardar un resultado y confirmar un mensaje.

Docker no estaba disponible en el equipo local. [GitHub Actions](https://github.com/Kill6r/nexo/actions)
ejecuta las pruebas con PostgreSQL y una prueba completa con Compose. No se ha hecho
una prueba de carga ni de despliegue.
