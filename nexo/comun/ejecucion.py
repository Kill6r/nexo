import asyncio
import signal


def ejecutar_servicio(servicio):
    async def iniciar():
        ciclo = asyncio.get_running_loop()
        tarea = asyncio.current_task()
        for senal in (signal.SIGTERM, signal.SIGINT):
            try:
                ciclo.add_signal_handler(senal, tarea.cancel)
            except NotImplementedError:
                pass
        try:
            await servicio()
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(iniciar())
    except KeyboardInterrupt:
        pass
