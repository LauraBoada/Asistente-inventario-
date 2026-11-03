from calculo.abastecimiento import armar_opciones, recomendar
from calculo.reposicion import es_critico, punto_de_reorden


def revisar_inventario(productos, catalogo, dias_seguridad=2, dias_cobertura=14, plazo_por_defecto=5):
    """Revisa todos los productos y devuelve qué hay que pedir.

    productos: lista de dicts (sku, titulo_producto, demanda_diaria, stock_actual,
               pedidos_en_camino, empaque).
    catalogo:  dict {sku: [filas de proveedores]}.
    Devuelve {"criticos": [...], "sin_proveedor": [skus]}. No toca la base de datos.
    """
    criticos, sin_proveedor = [], []

    for p in productos:
        filas = catalogo.get(p["sku"], [])
        # Para detectar usamos el plazo MÁS LARGO entre sus proveedores (criterio prudente)
        plazo_referencia = max((f["plazo_dias"] for f in filas), default=plazo_por_defecto)
        stock = p["stock_actual"] + p.get("pedidos_en_camino", 0)
        punto = punto_de_reorden(p["demanda_diaria"], plazo_referencia, dias_seguridad)

        if not es_critico(stock, punto):
            continue
        if not filas:
            sin_proveedor.append(p["sku"])
            continue

        opciones = armar_opciones(
            {"sku": p["sku"], "demanda_diaria": p["demanda_diaria"],
             "stock_disponible": stock, "empaque": p["empaque"]},
            filas, dias_cobertura,
        )
        criticos.append({
            "sku": p["sku"],
            "titulo_producto": p["titulo_producto"],
            "opciones": opciones,
            "recomendada": recomendar(opciones),
        })

    return {"criticos": criticos, "sin_proveedor": sin_proveedor}