import asyncio
import json
from types import SimpleNamespace

from grafo.clientes_mcp import llamar_lista


def test_llamar_lista_decodifica_cada_pedido_devuelto_por_mcp():
    class SesionFalsa:
        async def call_tool(self, herramienta, argumentos):
            assert herramienta == "reemplazar_pedidos"
            assert argumentos["nuevos"][0]["proveedor"] == "Proveedor A"
            return SimpleNamespace(
                isError=False,
                content=[
                    SimpleNamespace(text=json.dumps({
                        "pedido_id": "pedido-1",
                        "proveedor": "Proveedor A",
                        "productos": 1,
                        "total_cop": 1200,
                    })),
                    SimpleNamespace(text=json.dumps({
                        "pedido_id": "pedido-2",
                        "proveedor": "Proveedor B",
                        "productos": 2,
                        "total_cop": 2400,
                    })),
                ],
            )

    pedidos = asyncio.run(llamar_lista(
        SesionFalsa(),
        "reemplazar_pedidos",
        {"nuevos": [{"proveedor": "Proveedor A"}]},
    ))

    assert [pedido["proveedor"] for pedido in pedidos] == ["Proveedor A", "Proveedor B"]
    assert pedidos[0]["productos"] == 1
