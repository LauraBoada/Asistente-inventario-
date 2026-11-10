# Servidor MCP de solo lectura sobre el inventario. No expone ninguna herramienta de
# escritura: ni crea, ni modifica, ni borra nada en Mongo. Es el único MCP que el
# coordinador usa para "ver" el inventario (Agente Inventario).
#
# Ejecutar: python -m mcp_servers.mcp_inventario.server
from mcp.server.mcpserver import MCPServer

from calculo.datos import leer_catalogo, leer_productos, obtener_db

servidor = MCPServer("mcp-inventario")

_db = None


def _conexion():
    global _db
    if _db is None:
        _db = obtener_db()
    return _db


@servidor.tool()
def listar_productos() -> list[dict]:
    """Lista todos los productos del inventario, con stock, demanda y empaque."""
    return leer_productos(_conexion())


@servidor.tool()
def obtener_producto(sku: int) -> dict | None:
    """Devuelve un producto por su sku, o None si no existe en el inventario."""
    return next((p for p in leer_productos(_conexion()) if p["sku"] == sku), None)


@servidor.tool()
def obtener_catalogo_proveedores(sku: int) -> list[dict]:
    """Devuelve las filas del catálogo de proveedores de un sku (vacío si no tiene proveedor)."""
    return leer_catalogo(_conexion()).get(sku, [])


if __name__ == "__main__":
    servidor.run()
