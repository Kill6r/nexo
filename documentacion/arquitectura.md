# Arquitectura

La API, el publicador y los trabajadores corren como procesos separados. Comparten
PostgreSQL. Redis solo guarda los contadores temporales del limite de solicitudes.
RabbitMQ lleva mensajes con el ID del evento; los datos del evento quedan en PostgreSQL.

## Recorrido de un evento

1. La API comprueba el token y los datos recibidos.
2. Guarda el evento y una entrada pendiente en la misma transaccion. Responde 202.
3. El publicador toma la entrada con `FOR UPDATE SKIP LOCKED`, envia el ID a RabbitMQ
   y marca la entrada como publicada cuando recibe la confirmacion.
4. El trabajador bloquea la fila del evento, guarda el resultado y despues confirma
   el mensaje.
5. El cliente consulta el estado y el resultado desde la API.

La clave de idempotencia pertenece a cada usuario. Si llegan dos solicitudes con la
misma clave y los mismos datos, ambas apuntan al mismo evento. Si los datos cambian,
la API responde 409.

## Cuando algo falla

Si RabbitMQ deja de responder, los eventos aceptados siguen en la tabla `outbox`.
El publicador los reintenta. Si se detiene despues de enviar un mensaje y antes de
marcarlo como publicado, puede enviarlo otra vez. Por eso el trabajador revisa el
estado guardado antes de procesar.

Si falla el procesamiento, RabbitMQ devuelve el mensaje a la cola despues de cinco
segundos. Tras tres intentos, el evento queda como fallido y el mensaje pasa a la cola
de errores. Un mensaje invalido tambien va a esa cola.

La entrega es al menos una vez. En esta version los procesadores solo guardan
resultados en PostgreSQL. Una accion externa, como enviar un correo o cobrar un pago,
necesitaria su propia proteccion contra repeticiones.

## Colas y limites

Las colas se llaman `nexo.events.process`, `nexo.events.retry` y
`nexo.events.dead`. Esos nombres se conservan para no dejar mensajes existentes
en colas antiguas. Con varios trabajadores no hay un orden global garantizado.

El entorno local usa un solo RabbitMQ y colas clasicas. Para produccion harian falta
replicas, copias de seguridad, alertas y pruebas de recuperacion. Cambiar el tiempo de
reintento con mensajes en la cola requiere una migracion controlada.

## Acceso y seguimiento

Las claves se guardan con Argon2. Los JWT duran 30 minutos. Cada usuario solo puede
leer sus eventos. El registro y el acceso comparten un limite por IP; el envio de
eventos tiene otro limite por usuario.

Los registros JSON incluyen el ID del evento y el numero de intentos. No incluyen
claves ni el contenido del evento. La API ofrece `/salud/vivo`, `/salud/listo` y
`/metricas`. El publicador y los trabajadores se observan principalmente por sus
registros.

Los puertos locales solo escuchan en localhost. Antes de exponer Nexo en internet
harian falta TLS, secretos gestionados, proteccion de las metricas y de RabbitMQ,
limites de tamano, copias de seguridad y reglas para registrar usuarios.
