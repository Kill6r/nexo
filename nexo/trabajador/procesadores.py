import hashlib

from nexo.comun.esquemas import EventoNuevo


def calcular_resultado(evento):
    validado = EventoNuevo(tipo=evento.tipo, origen=evento.origen, datos=evento.datos)
    datos = validado.datos
    if evento.tipo == "github.repositorio.actualizado":
        estrellas = datos["estrellas"]
        return {
            "repositorio": datos["repositorio"],
            "estrellas": estrellas,
            "popularidad": "alta" if estrellas >= 10000 else "en crecimiento",
        }
    texto = datos["texto"]
    return {
        "caracteres": len(texto),
        "palabras": len(texto.split()),
        "sha256": hashlib.sha256(texto.encode()).hexdigest(),
    }
