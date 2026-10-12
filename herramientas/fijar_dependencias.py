import itertools
import tomllib
from importlib.metadata import distribution
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def dependencias(raices):
    elegidos = {}
    visitados = set()
    pendientes = [Requirement(raiz) for raiz in raices]
    entornos = []
    for version, plataforma in itertools.product(["3.12", "3.13"], ["win32", "linux"]):
        entorno = default_environment()
        entorno.update(
            python_version=version,
            python_full_version=version + ".0",
            sys_platform=plataforma,
            os_name="nt" if plataforma == "win32" else "posix",
            platform_system="Windows" if plataforma == "win32" else "Linux",
        )
        entornos.append(entorno)
    while pendientes:
        requisito = pendientes.pop()
        nombre = canonicalize_name(requisito.name)
        identidad = (nombre, tuple(sorted(requisito.extras)))
        if identidad in visitados:
            continue
        visitados.add(identidad)
        paquete = distribution(requisito.name)
        elegidos[nombre] = f"{paquete.metadata['Name']}=={paquete.version}"
        for linea in paquete.requires or []:
            secundario = Requirement(linea)
            extras = requisito.extras | {""}
            if secundario.marker is None or any(
                secundario.marker.evaluate({**entorno, "extra": extra})
                for entorno in entornos
                for extra in extras
            ):
                pendientes.append(secundario)
    return elegidos


def principal():
    proyecto = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    ejecucion = dependencias(proyecto["dependencies"])
    desarrollo = dependencias(proyecto["dependencies"] + proyecto["optional-dependencies"]["dev"])
    for archivo, paquetes in [
        ("requirements.lock", ejecucion),
        ("requirements-dev.lock", desarrollo),
    ]:
        lineas = []
        for nombre, version in sorted(paquetes.items()):
            if nombre == "colorama":
                version += '; sys_platform == "win32"'
            lineas.append(version)
        Path(archivo).write_text("\n".join(lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    principal()
