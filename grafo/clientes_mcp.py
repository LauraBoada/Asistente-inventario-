import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def servidor(archivo):
    """Arranca un servidor MCP de la carpeta mcp_servers/ y entrega la sesión."""
    parametros = StdioServerParameters(
        command=sys.executable,
        args=[str(RAIZ / "mcp_servers" / archivo)],
    )
    async with stdio_client(parametros) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()
            yield sesion


def _textos(resultado):
    textos = [bloque.text for bloque in resultado.content]
    if resultado.isError:
        raise RuntimeError(" ".join(textos))
    return textos


async def llamar(sesion, herramienta, argumentos=None):
    """Para herramientas que devuelven un solo objeto (o un texto)."""
    textos = _textos(await sesion.call_tool(herramienta, argumentos or {}))
    if not textos:
        return None
    try:
        return json.loads(textos[0])
    except ValueError:
        return textos[0]


async def llamar_lista(sesion, herramienta, argumentos=None):
    """Para herramientas que devuelven una lista (un bloque por elemento)."""
    textos = _textos(await sesion.call_tool(herramienta, argumentos or {}))
    return [json.loads(texto) for texto in textos]