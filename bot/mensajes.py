# Construye los textos y botones de la cotización, y traduce la respuesta del dueño
# (callback_data del botón que tocó) en la decisión que espera grafo.nodos.revisar_siguiente
# al reanudar el grafo. Separado de bot.py para poder probarlo sin conectarse a Telegram.


def formatear_cotizacion(cotizacion: dict) -> str:
    """Texto de la cotización de un producto crítico, con sus opciones de proveedor."""
    lineas = [
        f"📦 *{cotizacion['titulo_producto']}* (sku {cotizacion['sku']}) está por agotarse.",
        "",
        "Opciones de proveedor:",
    ]
    recomendado = (cotizacion.get("recomendada") or {}).get("proveedor")
    for opcion in cotizacion["opciones"]:
        marca = "✅ " if opcion["proveedor"] == recomendado else "• "
        tarde = " (llega tarde)" if opcion.get("llega_tarde") else ""
        lineas.append(
            f"{marca}{opcion['proveedor']}: {opcion['cantidad_a_pedir']} u. "
            f"— ${opcion['total_cop']:,.0f} COP{tarde}"
        )
    lineas.append("")
    lineas.append("✅ = opción recomendada. Elige un proveedor o rechaza el pedido.")
    return "\n".join(lineas)


def botones_cotizacion(cotizacion: dict) -> list[list[tuple[str, str]]]:
    """Filas de botones como (texto, callback_data), sin depender de la librería de
    Telegram: una fila por proveedor y una fila final para rechazar."""
    sku = cotizacion["sku"]
    recomendado = (cotizacion.get("recomendada") or {}).get("proveedor")
    filas = []
    for opcion in cotizacion["opciones"]:
        marca = "✅ " if opcion["proveedor"] == recomendado else ""
        texto = f"{marca}{opcion['proveedor']} ({opcion['cantidad_a_pedir']} u.)"
        filas.append([(texto, f"aprobar:{sku}:{opcion['proveedor']}")])
    filas.append([("❌ Rechazar", f"rechazar:{sku}")])
    return filas


def decision_desde_callback(data: str, aprobado_por: str) -> dict:
    """Traduce el callback_data de un botón ('aprobar:sku:proveedor' o 'rechazar:sku') en
    la decisión que espera el grafo al reanudar con Command(resume=...)."""
    accion, _, resto = data.partition(":")
    if accion == "aprobar":
        _sku, _, proveedor = resto.partition(":")
        return {"aprueba": True, "proveedor": proveedor, "aprobado_por": aprobado_por}
    return {"aprueba": False, "motivo": f"Rechazado por {aprobado_por} vía Telegram"}


def formatear_resumen(estado: dict) -> str:
    """Texto final cuando el grafo ya revisó todos los productos críticos (o se cortó por
    el límite de ciclos)."""
    lineas = ["📋 Revisión de inventario terminada."]

    enviados = [d for d in estado["decisiones"] if d["aprobado"]]
    simulados = [d for d in enviados if d.get("estado_envio", "simulado_enviado") == "simulado_enviado"]
    enviados_gmail = [d for d in enviados if d.get("estado_envio") == "enviado"]
    rechazados = [d for d in estado["decisiones"] if not d["aprobado"]]

    if simulados:
        lineas.append("")
        lineas.append(f"Pedidos enviados (simulado): {len(simulados)}")
        for d in simulados:
            lineas.append(f"• sku {d['sku']} — pedido {d['pedido_id']}")

    if enviados_gmail:
        lineas.append("")
        lineas.append(f"Pedidos enviados por Gmail: {len(enviados_gmail)}")
        for d in enviados_gmail:
            lineas.append(f"• sku {d['sku']} — pedido {d['pedido_id']}")

    if rechazados:
        lineas.append("")
        lineas.append(f"Sin enviar: {len(rechazados)}")
        for d in rechazados:
            lineas.append(f"• sku {d['sku']} — {d['motivo']}")

    if estado["sin_proveedor"]:
        lineas.append("")
        lineas.append(f"Críticos sin proveedor registrado: {estado['sin_proveedor']}")

    if not estado["criticos"]:
        lineas.append("")
        lineas.append("Ningún producto está en punto de reorden por ahora.")

    return "\n".join(lineas)
