import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RAIZ = Path(__file__).resolve().parent.parent
servidor = StdioServerParameters(
    command=sys.executable,
    args=[str(RAIZ / "mcp_servers" / "mcp_pedidos.py")],
)

ITEMS = [{"sku": 12097, "cantidad": 108, "precio_unitario_cop": 4320}]


async def llamar(sesion, herramienta, argumentos):
    resultado = await sesion.call_tool(herramienta, argumentos)
    texto = " ".join(bloque.text for bloque in resultado.content)
    if resultado.isError:
        print(f"[RECHAZADO] {herramienta}: {texto}")
        return None
    datos = json.loads(texto) if texto.startswith("{") else texto
    estado = datos.get("estado") if isinstance(datos, dict) else datos
    print(f"[ok]        {herramienta}: {estado}")
    return datos


async def main():
    async with stdio_client(servidor) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            await sesion.initialize()

            pedido = await llamar(sesion, "crear_borrador",
                                  {"proveedor": "Distribuidora Andina", "items": ITEMS})
            pid = pedido["pedido_id"]

            print("\n-- Intento 1: enviar sin aprobación (debe ser rechazado)")
            await llamar(sesion, "enviar_pedido", {"pedido_id": pid})

            print("\n-- El camino correcto")
            await llamar(sesion, "solicitar_aprobacion", {"pedido_id": pid})
            await llamar(sesion, "registrar_aprobacion", {"pedido_id": pid, "aprobado_por": "Dueño"})
            await llamar(sesion, "enviar_pedido", {"pedido_id": pid})

            print("\n-- Intento 2: enviar otra vez (debe ser rechazado)")
            await llamar(sesion, "enviar_pedido", {"pedido_id": pid})


asyncio.run(main())