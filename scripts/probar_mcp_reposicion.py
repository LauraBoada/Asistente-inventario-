import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent


def parametros(archivo):
    return StdioServerParameters(
        command=sys.executable,
        args=[str(RAIZ / "mcp_servers" / archivo)],
    )


async def con_servidor(archivo, tarea):
    """Arranca un servidor MCP, ejecuta la tarea y lo cierra."""
    async with stdio_client(parametros(archivo)) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()
            return await tarea(sesion)


async def leer_lista(sesion, herramienta):
    resultado = await sesion.call_tool(herramienta, {})
    return [json.loads(b.text) for b in resultado.content]


async def revisar(sesion, productos, catalogo):
    resultado = await sesion.call_tool(
        "revisar_inventario", {"productos": productos, "catalogo": catalogo})
    return json.loads(resultado.content[0].text)


async def main():
    # 1. Los datos se piden al servidor de inventario (el único que toca Atlas)
    productos = await con_servidor("mcp_inventario.py", lambda s: leer_lista(s, "consultar_inventario"))
    catalogo = await con_servidor("mcp_inventario.py", lambda s: leer_lista(s, "catalogo_proveedores"))

    # 2. El cálculo lo hace el servidor de reposición (no tiene acceso a la base)
    resultado = await con_servidor("mcp_reposicion.py", lambda s: revisar(s, productos, catalogo))

    print("Productos revisados:", len(productos))
    print("Críticos con proveedor:", len(resultado["criticos"]))
    print("Críticos sin proveedor:", resultado["sin_proveedor"])
    for c in resultado["criticos"]:
        r = c["recomendada"]
        print(f'  {c["sku"]}: pedir {r["cantidad_a_pedir"]} a {r["proveedor"]} '
              f'por ${r["total_cop"]:,} COP')


asyncio.run(main())