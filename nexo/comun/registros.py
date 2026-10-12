import json
import logging
from datetime import UTC, datetime


class FormatoJSON(logging.Formatter):
    def format(self, record):
        datos = {
            "fecha": datetime.now(UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": record.name,
            "mensaje": record.getMessage(),
        }
        for clave in ("id_evento", "id_solicitud", "estado", "intentos", "duracion_ms"):
            if hasattr(record, clave):
                datos[clave] = getattr(record, clave)
        if record.exc_info:
            datos["tipo_error"] = record.exc_info[0].__name__
        return json.dumps(datos)


def configurar_logs(nivel="INFO"):
    salida = logging.StreamHandler()
    salida.setFormatter(FormatoJSON())
    logging.basicConfig(level=nivel, handlers=[salida], force=True)
