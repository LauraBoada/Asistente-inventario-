import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent
servidor = StdioServerParameters(
    command=sys.executable,
    args=[str(RAIZ / "mcp_servers" / "mcp_inventario.py")],
)


async def llamar(sesion, herramienta, argumentos):
    print(f"\n--- {herramienta} {argumentos} ---")
    resultado = await sesion.call_tool(herramienta, argumentos)
    if not resultado.content:
        print("(sin resultados)")
    for bloque in resultado.content:
        print(bloque.text)


async def main():
    async with stdio_client(servidor) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()

            await llamar(sesion, "consultar_inventario", {"sku": 12097})
            await llamar(sesion, "historial_ventas", {"sku": 12097, "dias": 5})
            await llamar(sesion, "catalogo_proveedores", {"sku": 12097})
            await llamar(sesion, "consultar_inventario", {"sku": 999})   # no existe


asyncio.run(main())