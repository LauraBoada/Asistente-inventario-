import sys
from pathlib import Path

# Permite importar la carpeta calculo/ aunque el servidor se lance desde otro lugar
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from calculo.reposicion import cantidad_sugerida
from calculo.revision import revisar_inventario as revisar

mcp = FastMCP("reposicion")


@mcp.tool()
def revisar_inventario(productos: list[dict], catalogo: list[dict],
                       dias_seguridad: int = 2, dias_cobertura: int = 14) -> dict:
    """Detecta los productos críticos (a punto de agotarse) y calcula cuánto pedir.

    productos: lista con sku, titulo_producto, demanda_diaria, stock_actual,
               pedidos_en_camino y empaque.
    catalogo: filas de proveedores con sku, proveedor, precio_unitario_cop,
              plazo_dias y pedido_minimo_unidades.
    Devuelve los críticos con una opción por proveedor y la recomendada,
    y la lista de críticos que ningún proveedor surte."""
    por_sku = {}
    for fila in catalogo:
        por_sku.setdefault(fila["sku"], []).append(fila)
    return revisar(productos, por_sku, dias_seguridad, dias_cobertura)


@mcp.tool()
def calcular_cantidad(demanda_diaria: float, plazo_dias: int, dias_cobertura: int,
                      stock_disponible: float, empaque: int, pedido_minimo: int) -> int:
    """Cantidad a pedir de un producto: cubre el plazo y los días de cobertura,
    se redondea al empaque y respeta el pedido mínimo del proveedor."""
    return cantidad_sugerida(demanda_diaria, plazo_dias, dias_cobertura,
                             stock_disponible, empaque, pedido_minimo)


if __name__ == "__main__":
    mcp.run()