# Decisiones tecnicas

## RabbitMQ

Se eligio RabbitMQ porque los trabajos son independientes y necesitan confirmacion,
reintentos y una cola de errores. Kafka tendria mas sentido si luego hicieran falta
flujos conservados o varios grupos de consumidores.

## Eventos pendientes

La API guarda el evento y la solicitud de publicacion en una sola transaccion. Asi,
una caida de RabbitMQ no hace desaparecer un evento ya aceptado. El costo es un
proceso adicional y un pequeno retraso antes de publicarlo.

## Base de datos compartida

La API, el publicador y el trabajador comparten modelos y base de datos en esta
primera version. Es mas sencillo de ejecutar, aunque obliga a coordinar los cambios
de esquema. Si se agregan servicios de analisis o notificaciones, necesitaran
contratos de mensajes versionados y datos propios.

## Mensajes repetidos

PostgreSQL impide duplicados al recibir un evento. El trabajador bloquea la fila y
omite los eventos terminados. Redis limita solicitudes, pero el procesamiento no
depende de su contenido para ser correcto.

## Seguimiento

Por ahora hay registros JSON, ID por solicitud, metricas HTTP y comprobaciones de
salud. Quedan pendientes las metricas del publicador y los trabajadores, alertas y
trazas entre servicios.
