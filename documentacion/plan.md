# Plan

## Version actual

La API, PostgreSQL, RabbitMQ, Redis, el publicador y el trabajador ya funcionan
juntos. Hay JWT, migraciones, reintentos con limite, cola de errores, pruebas y
GitHub Actions.

## Siguiente paso

- Medir cuanto tiempo esperan los eventos antes de publicarse.
- Avisar cuando crezca la cola de errores.
- Anadir metricas y trazas para el publicador y el trabajador.
- Probar caidas de PostgreSQL y varios trabajadores bajo carga.
- Definir limpieza de eventos pendientes y recuperacion de mensajes fallidos.
- Limitar el tamano de cada evento y la cantidad de trabajo acumulado.

## Despues

Un panel para ver estados y resultados puede ayudar a usar el proyecto. Tambien
quedan por revisar una cache de resultados en Redis, la recepcion de webhooks reales
de GitHub y servicios separados de analisis y notificaciones.

Antes de desplegarlo harian falta un entorno de pruebas, TLS, secretos gestionados,
un RabbitMQ con replicas, una estrategia de migraciones y pruebas de restauracion.
No hay cifras de rendimiento o disponibilidad hasta medirlas.
