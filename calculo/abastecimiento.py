#Arma las opciones por proveedor (cantidad, total, si llega tarde) y marca la recomendada. Es el Agente Abastecimiento
from calculo.reposicion import cantidad_sugerida


def armar_opciones(producto, catalogo, dias_cobertura):
    """Una opción por cada proveedor que surte el producto.

    producto: dict con sku, demanda_diaria, stock_disponible y empaque.
    catalogo: lista de dicts con proveedor, precio_unitario_cop, plazo_dias
              y pedido_minimo_unidades (solo las filas de ese producto).
    """
    demanda = producto["demanda_diaria"]
    stock = producto["stock_disponible"]
    dias_de_stock = stock / demanda if demanda > 0 else float("inf")

    opciones = []
    for fila in catalogo:
        cantidad = cantidad_sugerida(
            demanda=demanda,
            plazo=fila["plazo_dias"],
            dias_cobertura=dias_cobertura,
            stock_disponible=stock,
            empaque=producto["empaque"],
            pedido_minimo=fila["pedido_minimo_unidades"],
        )
        opciones.append({
            "sku": producto["sku"],
            "proveedor": fila["proveedor"],
            "plazo_dias": fila["plazo_dias"],
            "empaque": producto["empaque"],
            "pedido_minimo_unidades": fila["pedido_minimo_unidades"],
            "cantidad_a_pedir": cantidad,
            "precio_unitario_cop": fila["precio_unitario_cop"],
            "total_cop": cantidad * fila["precio_unitario_cop"],
            "llega_tarde": dias_de_stock < fila["plazo_dias"],
        })
    return opciones


def recomendar(opciones):
    """Elige la opción recomendada y explica por qué. Devuelve None si no hay opciones."""
    if not opciones:
        return None

    a_tiempo = [o for o in opciones if not o["llega_tarde"]]
    if a_tiempo:
        elegida = min(a_tiempo, key=lambda o: o["total_cop"])
        motivo = "Menor costo total entre los que llegan a tiempo"
    else:
        elegida = min(opciones, key=lambda o: (o["plazo_dias"], o["total_cop"]))
        motivo = "Ninguno llega a tiempo: el más rápido"
    return {**elegida, "motivo": motivo}