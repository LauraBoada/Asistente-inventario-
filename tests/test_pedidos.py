import pytest

from calculo.pedidos import (
    ErrorDePedido, aprobar, crear_borrador, marcar_enviado, marcar_fallido,
    marcar_pendiente, pedir_aprobacion, rechazar,
)

ITEMS = [
    {"sku": 12097, "cantidad": 108, "precio_unitario_cop": 4320},
    {"sku": 83810, "cantidad": 72, "precio_unitario_cop": 6210},
]


def pedido_aprobado():
    p = crear_borrador("Distribuidora Andina", ITEMS)
    p = pedir_aprobacion(p)
    return aprobar(p, aprobado_por="Dueño")


def test_crear_borrador_calcula_el_total():
    p = crear_borrador("Distribuidora Andina", ITEMS)
    assert p["estado"] == "borrador"
    assert p["total_cop"] == 108 * 4320 + 72 * 6210
    assert p["aprobado_por"] is None and p["enviado_en"] is None


def test_borrador_invalido():
    with pytest.raises(ErrorDePedido):
        crear_borrador("Distribuidora Andina", [])
    with pytest.raises(ErrorDePedido):
        crear_borrador("", ITEMS)
    with pytest.raises(ErrorDePedido):
        crear_borrador("Distribuidora Andina", [{"sku": 1, "cantidad": 0, "precio_unitario_cop": 10}])


def test_camino_feliz_hasta_el_envio():
    p = pedido_aprobado()
    assert p["estado"] == "aprobado"
    assert p["aprobado_por"] == "Dueño" and p["aprobado_en"] is not None
    p = marcar_enviado(p)
    assert p["estado"] == "enviado" and p["enviado_en"] is not None


def test_no_se_puede_enviar_sin_aprobacion():
    borrador = crear_borrador("Distribuidora Andina", ITEMS)
    with pytest.raises(ErrorDePedido):
        marcar_enviado(borrador)
    with pytest.raises(ErrorDePedido):
        marcar_enviado(pedir_aprobacion(borrador))


def test_no_se_puede_enviar_dos_veces():
    enviado = marcar_enviado(pedido_aprobado())
    with pytest.raises(ErrorDePedido):
        marcar_enviado(enviado)


def test_no_se_puede_aprobar_un_borrador_directamente():
    with pytest.raises(ErrorDePedido):
        aprobar(crear_borrador("Distribuidora Andina", ITEMS), aprobado_por="Dueño")


def test_aprobar_exige_registrar_quien_aprueba():
    p = pedir_aprobacion(crear_borrador("Distribuidora Andina", ITEMS))
    with pytest.raises(ErrorDePedido):
        aprobar(p, aprobado_por="")


def test_pedido_de_alto_valor_exige_confirmacion_reforzada():
    p = pedir_aprobacion(crear_borrador("Distribuidora Andina", ITEMS))   # total 913.680
    with pytest.raises(ErrorDePedido):
        aprobar(p, aprobado_por="Dueño", umbral_alto_valor=500_000)
    ok = aprobar(p, aprobado_por="Dueño", umbral_alto_valor=500_000, confirmacion_reforzada=True)
    assert ok["estado"] == "aprobado"
    # Si el pedido no supera el umbral, no hace falta
    assert aprobar(p, aprobado_por="Dueño", umbral_alto_valor=2_000_000)["estado"] == "aprobado"


def test_rechazado_o_pendiente_nunca_se_envian():
    p = pedir_aprobacion(crear_borrador("Distribuidora Andina", ITEMS))
    with pytest.raises(ErrorDePedido):
        marcar_enviado(rechazar(p, motivo="Muy caro"))
    with pytest.raises(ErrorDePedido):
        marcar_enviado(marcar_pendiente(p))


def test_un_pedido_rechazado_ya_no_se_puede_aprobar():
    rechazado = rechazar(pedir_aprobacion(crear_borrador("Distribuidora Andina", ITEMS)))
    with pytest.raises(ErrorDePedido):
        aprobar(rechazado, aprobado_por="Dueño")


def test_envio_fallido_queda_registrado_y_no_se_reenvia():
    fallido = marcar_fallido(pedido_aprobado(), motivo="El correo rebotó")
    assert fallido["estado"] == "fallido" and fallido["motivo"] == "El correo rebotó"
    with pytest.raises(ErrorDePedido):
        marcar_enviado(fallido)


def test_las_funciones_no_modifican_el_pedido_original():
    original = crear_borrador("Distribuidora Andina", ITEMS)
    pedir_aprobacion(original)
    assert original["estado"] == "borrador"