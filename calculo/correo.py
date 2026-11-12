"""Construcción de mensajes de pedido para simulación y envío por correo."""

from datetime import datetime


MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def resolver_destinatario(destinatario_proveedor, modo, destinatario_pruebas=None):
    """Usa un destinatario de prueba solo cuando el envío Gmail real está activado."""
    if modo == "gmail" and destinatario_pruebas and destinatario_pruebas.strip():
        return destinatario_pruebas.strip()
    return destinatario_proveedor


def preparar_correo(pedido, destinatario):
    ahora = datetime.now()
    periodo = f"{MESES[ahora.month - 1]} de {ahora.year}"
    lineas = [
        f"Estimado equipo de {pedido['proveedor']}:",
        "",
        f"Reciban un cordial saludo. Les compartimos nuestra solicitud de reposición "
        f"correspondiente a {periodo}:",
        "",
    ]
    for item in pedido["items"]:
        lineas.append(
            f"- SKU {item['sku']}: {item['cantidad']} unidades "
            f"a ${item['precio_unitario_cop']:,.0f} COP c/u"
        )
    lineas += [
        "",
        f"Total: ${pedido['total_cop']:,.0f} COP",
        "",
        "Agradecemos confirmar la disponibilidad de los productos y la fecha estimada "
        "de entrega.",
        "",
        "Quedamos atentos. Muchas gracias por su atención.",
    ]
    return {
        "destinatario": destinatario or "No registrado en el catálogo",
        "asunto": f"Pedido de reposición - {pedido['proveedor']}",
        "cuerpo": "\n".join(lineas),
    }
