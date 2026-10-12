import aio_pika

from nexo.comun.esquemas import MensajeEvento

INTERCAMBIO_EVENTOS = "nexo.events"
INTERCAMBIO_REINTENTOS = "nexo.retry"
INTERCAMBIO_ERRORES = "nexo.dead"
COLA_EVENTOS = "nexo.events.process"
COLA_REINTENTOS = "nexo.events.retry"
COLA_ERRORES = "nexo.events.dead"
CLAVE_RUTA = "process"


class ColaRabbit:
    def __init__(self, url: str, demora_reintento_ms: int):
        self.url = url
        self.demora_reintento_ms = demora_reintento_ms
        self.conexion = None

    async def conectar(self):
        self.conexion = await aio_pika.connect_robust(self.url, timeout=10)
        self.canal = await self.conexion.channel(publisher_confirms=True, on_return_raises=True)
        await self.canal.set_qos(prefetch_count=10)
        self.intercambio = await self.canal.declare_exchange(
            INTERCAMBIO_EVENTOS, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.intercambio_reintentos = await self.canal.declare_exchange(
            INTERCAMBIO_REINTENTOS, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.intercambio_errores = await self.canal.declare_exchange(
            INTERCAMBIO_ERRORES, aio_pika.ExchangeType.DIRECT, durable=True
        )
        errores = await self.canal.declare_queue(COLA_ERRORES, durable=True)
        await errores.bind(self.intercambio_errores, CLAVE_RUTA)
        self.cola = await self.canal.declare_queue(
            COLA_EVENTOS,
            durable=True,
            arguments={
                "x-dead-letter-exchange": INTERCAMBIO_ERRORES,
                "x-dead-letter-routing-key": CLAVE_RUTA,
            },
        )
        await self.cola.bind(self.intercambio, CLAVE_RUTA)
        reintentos = await self.canal.declare_queue(
            COLA_REINTENTOS,
            durable=True,
            arguments={
                "x-message-ttl": self.demora_reintento_ms,
                "x-dead-letter-exchange": INTERCAMBIO_EVENTOS,
                "x-dead-letter-routing-key": CLAVE_RUTA,
            },
        )
        await reintentos.bind(self.intercambio_reintentos, CLAVE_RUTA)

    async def publicar(self, id_evento, *, reintento=False):
        sobre = MensajeEvento(event_id=id_evento)
        mensaje = aio_pika.Message(
            sobre.model_dump_json().encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(id_evento),
        )
        intercambio = self.intercambio_reintentos if reintento else self.intercambio
        await intercambio.publish(mensaje, routing_key=CLAVE_RUTA, mandatory=True, timeout=10)

    async def verificar(self):
        if not self.conexion or self.conexion.is_closed:
            raise ConnectionError("RabbitMQ no esta disponible")
        await self.canal.declare_queue(COLA_EVENTOS, passive=True, timeout=3)

    async def cerrar(self):
        if self.conexion:
            await self.conexion.close()
