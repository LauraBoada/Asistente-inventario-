import sys
from pathlib import Path

# Permite importar la carpeta calculo/ aunque el servidor se lance desde otro lugar
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from calculo.proveedores import crear_cotizacion
from calculo.datos import obtener_db

mcp = FastMCP("inventario")
db = obtener_db()


@mcp.tool()
def consultar_inventario(sku: int | None = None) -> list[dict]:
    """Devuelve el inventario actual: stock, empaque, demanda diaria y precio de cada producto.
    Si se indica un sku, devuelve solo ese producto."""
    filtro = {"sku": sku} if sku is not None else {}
    campos = {"_id": 0, "sku": 1, "titulo_producto": 1, "stock_actual": 1,
              "pedidos_en_camino": 1, "empaque": 1, "minimo_manual": 1,
              "demanda_diaria": 1, "precio_cop_actual": 1}
    return list(db["productos"].find(filtro, campos))


@mcp.tool()
def historial_ventas(sku: int, dias: int = 30) -> list[dict]:
    """Ventas diarias de un producto en sus últimos N días (la más reciente primero)."""
    dias = max(1, min(dias, 365))
    campos = {"_id": 0, "sku": 1, "fecha": 1, "cantidad_vendida": 1, "dias_activos": 1}
    filas = db["ventas"].find({"sku": sku}, campos).sort("fecha", -1).limit(dias)
    return [{**f, "fecha": f["fecha"].date().isoformat()} for f in filas]


@mcp.tool()
def catalogo_proveedores(sku: int | None = None) -> list[dict]:
    """Proveedores que surten un producto, con precio unitario, plazo y pedido mínimo.
    Si no se indica sku, devuelve todo el catálogo."""
    filtro = {"sku": sku} if sku is not None else {}
    return list(db["catalogo_proveedores"].find(filtro, {"_id": 0}))


@mcp.tool()
def agregar_cotizacion(
    sku: int,
    proveedor: str,
    precio_unitario_cop: int,
    plazo_dias: int,
    pedido_minimo_unidades: int,
    contacto: str = "",
) -> dict:
    """Agrega o actualiza una cotización de un producto crítico sin proveedor.

    El precio se informa en COP por unidad. Un correo de contacto es opcional.
    """
    fila = crear_cotizacion(
        sku,
        proveedor,
        precio_unitario_cop,
        plazo_dias,
        pedido_minimo_unidades,
        contacto,
    )
    if db["productos"].find_one({"sku": sku}, {"_id": 1}) is None:
        raise ValueError(f"No existe el SKU {sku} en la colección productos.")

    cotizacion = {k: v for k, v in fila.items() if k != "contacto"}
    db["catalogo_proveedores"].update_one(
        {"sku": sku, "proveedor": cotizacion["proveedor"]},
        {"$set": cotizacion},
        upsert=True,
    )
    if fila.get("contacto"):
        db["proveedores"].update_one(
            {"proveedor": proveedor},
            {"$set": {"contacto": fila["contacto"]}},
            upsert=True,
        )
    return fila


if __name__ == "__main__":
    mcp.run()