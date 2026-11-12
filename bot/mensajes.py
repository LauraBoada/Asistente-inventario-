"""Textos que ve el dueño en Telegram. Son funciones simples, sin Telegram, para poder probarlas."""

LIMITE = 3900   # Telegram admite 4096 caracteres por mensaje


def _cop(valor):
    return f"${valor:,.0f}"


def _lineas_producto(c, detallado):
    titulo = c["titulo"].strip()[:40]
    lineas = [f"• {titulo} ({c['sku']})"]
    for o in c["opciones"]:
        recomendada = o.get("recomendada", o["proveedor"] == c["recomendada"])
        seleccionada = o.get(
            "seleccionada",
            o["proveedor"] == c.get("seleccionada", c["recomendada"]),
        )
        if not detallado and not recomendada and not seleccionada:
            continue
        marca = "⭐✅" if recomendada and seleccionada else (
            "✅" if seleccionada else ("⭐" if recomendada else "▫️")
        )
        tarde = " ⚠️ llega tarde" if o["llega_tarde"] else ""
        lineas.append(f"   {marca} {o['proveedor']}: {o['cantidad']} unid. · "
                      f"{_cop(o['total_cop'])} · {o['plazo_dias']} días{tarde}")
    return lineas


def _construir(info, detallado, max_productos=None):
    todos = info.get("criticos", [])
    criticos = todos if max_productos is None else todos[:max_productos]
    lineas = []
    mensaje = info.get("mensaje", "")
    if mensaje and not mensaje.startswith("Pedidos listos"):
        lineas += [mensaje, ""]
    lineas += ["📦 Revisión de inventario", "", f"Productos por agotarse: {len(todos)}"]
    for c in criticos:
        lineas.append("")
        lineas += _lineas_producto(c, detallado)
    if len(criticos) < len(todos):
        lineas += ["", f"… y {len(todos) - len(criticos)} productos más (incluidos en los pedidos)"]
    if any(c.get("seleccionada") and c["seleccionada"] != c["recomendada"] for c in criticos):
        lineas += ["", "⭐ Recomendación · ✅ opción que elegiste"]
    lineas += ["", "Pedidos que se crearían si apruebas:"]
    for p in info.get("pedidos", []):
        cantidad = p["productos"]
        unidad = "producto" if cantidad == 1 else "productos"
        lineas.append(f"   - {p['proveedor']}: {cantidad} {unidad} · {_cop(p['total_cop'])}")
    if info.get("sin_proveedor"):
        lineas += ["", "⚠️ Cotización pendiente para estos SKU: "
                   + ", ".join(str(s) for s in info["sin_proveedor"])]
        lineas += [
            "Pulsa «Agregar cotización» y envía los datos del proveedor por este chat."
        ]
    return "\n".join(lineas)


def formatear_cotizacion(info):
    """Cotización completa; si es muy larga, muestra solo la opción recomendada de cada producto."""
    texto = _construir(info, detallado=True)
    if len(texto) > LIMITE:
        texto = _construir(info, detallado=False)
    # Si aún es muy larga, se muestran menos productos, pero el resumen de pedidos siempre queda
    n = len(info.get("criticos", []))
    while len(texto) > LIMITE and n > 0:
        n -= 1
        texto = _construir(info, detallado=False, max_productos=n)
    return texto


ETIQUETAS = {
    "enviado": "✅ Pedidos enviados",
    "simulado": "🧪 Pedido simulado: no se envió ningún correo.",
    "enviado_con_errores": "⚠️ Algunos pedidos no se pudieron enviar",
    "rechazado": "❌ Pedidos rechazados. No se envió nada.",
    "pendiente": "⏳ Los pedidos quedaron pendientes. No se envió nada.",
    "sin_novedades": "✅ Todo en orden: no hay productos por agotarse.",
    "solo_sin_proveedor": "⚠️ Hay productos por agotarse, pero ningún proveedor los surte.",
}


def formatear_resultado(resultado):
    texto = ETIQUETAS.get(resultado["resultado"], resultado["resultado"])
    lineas = [texto]
    if resultado.get("sin_proveedor"):
        lineas.append(
            "⚠️ Sin proveedor: " + ", ".join(str(sku) for sku in resultado["sin_proveedor"])
        )
        lineas.append(
            "No se genera pedido para esos SKU hasta añadir una cotización a "
            "catalogo_proveedores."
        )
    for p in resultado.get("pedidos", []):
        if "estado" in p:
            lineas.append(f"   - {p['proveedor']}: {p['estado']}")
        if p.get("detalle"):
            lineas.append(f"      Motivo: {p['detalle']}")
        correo = p.get("correo")
        if correo and correo.get("canal") == "simulado":
            lineas.append(f"      Para: {correo['destinatario']}")
            lineas.append(f"      Asunto: {correo['asunto']}")
            lineas.append("      Vista previa (no enviada):")
            lineas.extend(f"      {fila}" for fila in correo["cuerpo"].splitlines()[:8])
    return "\n".join(lineas)