"""Validación de datos de una cotización de proveedor."""


def crear_cotizacion(
    sku,
    proveedor,
    precio_unitario_cop,
    plazo_dias,
    pedido_minimo_unidades,
    contacto=None,
):
    nombre = proveedor.strip() if isinstance(proveedor, str) else ""
    if not nombre:
        raise ValueError("El proveedor no puede quedar vacío.")
    if isinstance(sku, bool) or not isinstance(sku, int) or sku <= 0:
        raise ValueError("El SKU debe ser un entero positivo.")
    if (isinstance(precio_unitario_cop, bool)
            or not isinstance(precio_unitario_cop, int)
            or precio_unitario_cop <= 0):
        raise ValueError("El precio unitario debe ser un entero en COP mayor que cero.")
    if isinstance(plazo_dias, bool) or not isinstance(plazo_dias, int) or plazo_dias <= 0:
        raise ValueError("El plazo de entrega debe ser un entero de días mayor que cero.")
    if (isinstance(pedido_minimo_unidades, bool)
            or not isinstance(pedido_minimo_unidades, int)
            or pedido_minimo_unidades <= 0):
        raise ValueError("El pedido mínimo debe ser un entero mayor que cero.")

    correo = contacto.strip() if isinstance(contacto, str) else ""
    if correo and ("@" not in correo or "." not in correo.rsplit("@", 1)[-1]):
        raise ValueError("El correo de contacto no parece válido.")

    fila = {
        "sku": sku,
        "proveedor": nombre,
        "precio_unitario_cop": precio_unitario_cop,
        "plazo_dias": plazo_dias,
        "pedido_minimo_unidades": pedido_minimo_unidades,
    }
    if correo:
        fila["contacto"] = correo
    return fila


def leer_cotizacion_chat(texto, skus_pendientes):
    """Interpreta la línea de cotización enviada por el dueño en Telegram."""
    campos = [campo.strip() for campo in texto.split("|")]
    if len(campos) not in (5, 6):
        raise ValueError(
            "Usa este formato, separado con |:\n"
            "SKU | proveedor | precio unitario COP | días de entrega | pedido mínimo | correo opcional"
        )
    try:
        sku, proveedor = int(campos[0]), campos[1]
        precio, plazo, minimo = map(int, campos[2:5])
    except ValueError as error:
        raise ValueError(
            "SKU, precio, días y pedido mínimo deben ser números enteros. "
            "Escribe el precio en COP sin puntos ni comas."
        ) from error
    if sku not in skus_pendientes:
        disponibles = ", ".join(str(s) for s in skus_pendientes)
        raise ValueError(f"El SKU debe ser uno de los pendientes de cotización: {disponibles}.")
    contacto = campos[5] if len(campos) == 6 and campos[5].lower() not in ("-", "ninguno") else ""
    return crear_cotizacion(sku, proveedor, precio, plazo, minimo, contacto)
