from datetime import datetime, timezone

# Estados de un pedido (Anexo D de la guía)
BORRADOR = "borrador"
ESPERANDO = "esperando_aprobacion"
APROBADO = "aprobado"
ENVIADO = "enviado"
RECHAZADO = "rechazado"
PENDIENTE = "pendiente"
FALLIDO = "fallido"


class ErrorDePedido(Exception):
    """Se intentó una acción que las reglas del pedido no permiten."""


def _ahora():
    return datetime.now(timezone.utc)


def _exigir_estado(pedido, *permitidos, accion):
    if pedido["estado"] not in permitidos:
        raise ErrorDePedido(
            f"No se puede {accion} un pedido en estado '{pedido['estado']}'")


def crear_borrador(proveedor, items, ahora=None):
    """Arma un pedido nuevo en estado borrador.

    items: lista de dicts con sku, cantidad y precio_unitario_cop.
    """
    if not proveedor:
        raise ErrorDePedido("El pedido necesita un proveedor")
    if not items:
        raise ErrorDePedido("El pedido necesita al menos un producto")
    for item in items:
        if item["cantidad"] <= 0:
            raise ErrorDePedido("La cantidad de cada producto debe ser mayor que cero")
        if item["precio_unitario_cop"] < 0:
            raise ErrorDePedido("El precio no puede ser negativo")

    return {
        "proveedor": proveedor,
        "items": [dict(i) for i in items],
        "total_cop": sum(i["cantidad"] * i["precio_unitario_cop"] for i in items),
        "estado": BORRADOR,
        "version": 1,
        "creado_en": ahora or _ahora(),
        "aprobado_por": None,
        "aprobado_en": None,
        "enviado_en": None,
        "motivo": None,
    }


def pedir_aprobacion(pedido):
    """El borrador se le presenta al dueño y queda esperando su respuesta."""
    _exigir_estado(pedido, BORRADOR, accion="pedir aprobación de")
    return {**pedido, "estado": ESPERANDO}


def aprobar(pedido, aprobado_por, confirmacion_reforzada=False,
            umbral_alto_valor=None, ahora=None):
    """Registra quién aprobó y cuándo. Si el pedido es de alto valor,
    exige además una confirmación reforzada."""
    _exigir_estado(pedido, ESPERANDO, accion="aprobar")
    if not aprobado_por:
        raise ErrorDePedido("Hay que registrar quién aprueba el pedido")
    if (umbral_alto_valor is not None and pedido["total_cop"] >= umbral_alto_valor
            and not confirmacion_reforzada):
        raise ErrorDePedido("Pedido de alto valor: falta la confirmación reforzada")
    return {**pedido, "estado": APROBADO, "aprobado_por": aprobado_por,
            "aprobado_en": ahora or _ahora()}


def rechazar(pedido, motivo=None):
    _exigir_estado(pedido, ESPERANDO, accion="rechazar")
    return {**pedido, "estado": RECHAZADO, "motivo": motivo}


def marcar_pendiente(pedido):
    """El dueño no respondió a tiempo: el pedido queda pendiente, sin enviarse."""
    _exigir_estado(pedido, ESPERANDO, accion="dejar pendiente")
    return {**pedido, "estado": PENDIENTE}


def marcar_enviado(pedido, ahora=None):
    """Solo se puede enviar un pedido aprobado, con aprobación registrada,
    y nunca dos veces."""
    if pedido["estado"] == ENVIADO:
        raise ErrorDePedido("Este pedido ya fue enviado")
    _exigir_estado(pedido, APROBADO, accion="enviar")
    if not pedido["aprobado_por"] or not pedido["aprobado_en"]:
        raise ErrorDePedido("No hay una aprobación registrada para este pedido")
    return {**pedido, "estado": ENVIADO, "enviado_en": ahora or _ahora()}
 

def marcar_fallido(pedido, motivo):
    """El envío falló (después de los reintentos)."""
    _exigir_estado(pedido, APROBADO, accion="marcar como fallido")
    return {**pedido, "estado": FALLIDO, "motivo": motivo}