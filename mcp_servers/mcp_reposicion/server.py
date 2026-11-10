# Servidor MCP de la fórmula de reposición. No toca Mongo: solo recibe datos (productos,
# catálogo) y calcula punto de reorden, producto crítico, cantidad sugerida y la opción de
# proveedor recomendada. El coordinador le pasa lo que ya leyó de mcp-inventario.
#
# Ejecutar: python -m mcp_servers.mcp_reposicion.server
from mcp.server.mcpserver import MCPServer

from calculo.abastecimiento import armar_opciones, recomendar
from calculo.reposicion import cantidad_sugerida, es_critico, punto_de_reorden
from calculo.revision import revisar_inventario

servidor = MCPServer("mcp-reposicion")


@servidor.tool()
def calcular_punto_reorden(demanda_diaria: float, plazo_dias: float, dias_seguridad: float = 2) -> float:
    """Nivel de stock a partir del cual un producto hay que reponerlo."""
    return punto_de_reorden(demanda_diaria, plazo_dias, dias_seguridad)


@servidor.tool()
def es_producto_critico(stock_disponible: float, punto_reorden: float) -> bool:
    """True si el stock disponible ya llegó al punto de reorden o por debajo."""
    return es_critico(stock_disponible, punto_reorden)


@servidor.tool()
def calcular_cantidad_sugerida(
    demanda_diaria: float,
    plazo_dias: float,
    dias_cobertura: float,
    stock_disponible: float,
    empaque: int,
    pedido_minimo: int,
) -> int:
    """Unidades a pedir: demanda x (plazo + cobertura) - stock, al múltiplo del empaque y
    nunca menor al pedido mínimo del proveedor."""
    return cantidad_sugerida(demanda_diaria, plazo_dias, dias_cobertura, stock_disponible, empaque, pedido_minimo)


@servidor.tool()
def armar_opciones_proveedor(producto: dict, catalogo: list[dict], dias_cobertura: float = 14) -> list[dict]:
    """Una opción de compra por cada proveedor del catálogo de ese producto."""
    return armar_opciones(producto, catalogo, dias_cobertura)


@servidor.tool()
def recomendar_proveedor(opciones: list[dict]) -> dict | None:
    """Elige la mejor opción de proveedor (menor costo entre los que llegan a tiempo)."""
    return recomendar(opciones)


@servidor.tool()
def revisar_inventario_completo(
    productos: list[dict],
    catalogo: dict,
    dias_seguridad: float = 2,
    dias_cobertura: float = 14,
    plazo_por_defecto: float = 5,
) -> dict:
    """Revisa una lista de productos y devuelve los críticos (con sus opciones y
    recomendación) y los críticos que no tienen proveedor. No toca la base de datos."""
    return revisar_inventario(productos, catalogo, dias_seguridad, dias_cobertura, plazo_por_defecto)


if __name__ == "__main__":
    servidor.run()
