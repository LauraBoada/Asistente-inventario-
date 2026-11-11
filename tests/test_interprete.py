from bot.interprete import Intencion, validar_intencion


COTIZACION = {
    "titulo_producto": "Funda crítica",
    "opciones": [
        {
            "proveedor": "Distribuidora Andina",
            "cantidad_a_pedir": 48,
            "precio_unitario_cop": 100,
            "total_cop": 4800,
            "empaque": 12,
            "pedido_minimo_unidades": 12,
        },
        {
            "proveedor": "Mayorista Central",
            "cantidad_a_pedir": 72,
            "precio_unitario_cop": 90,
            "total_cop": 6480,
            "empaque": 24,
            "pedido_minimo_unidades": 48,
        },
    ],
    "recomendada": {"proveedor": "Distribuidora Andina"},
}


def test_aprobar_mitad_usa_recomendado_y_valida_empaque():
    resultado = validar_intencion(Intencion(accion="aprobar", fraccion=0.5), COTIZACION, "Laura")

    assert resultado["decision"] == {
        "aprueba": True,
        "proveedor": "Distribuidora Andina",
        "aprobado_por": "Laura",
        "cantidad": 24,
    }
    assert resultado["aclaracion"] is None


def test_cantidad_que_no_cumple_empaque_se_envia_a_botones():
    resultado = validar_intencion(Intencion(accion="aprobar", cantidad=18), COTIZACION, "Laura")

    assert resultado["decision"] is None
    assert "empaque o pedido mínimo" in resultado["aclaracion"]


def test_cantidad_menor_al_minimo_se_envia_a_botones():
    resultado = validar_intencion(
        Intencion(accion="aprobar", proveedor="Mayorista Central", cantidad=24),
        COTIZACION,
        "Laura",
    )

    assert resultado["decision"] is None
    assert "empaque o pedido mínimo" in resultado["aclaracion"]


def test_proveedor_que_no_existe_se_envia_a_botones():
    resultado = validar_intencion(Intencion(accion="aprobar", proveedor="Otro proveedor"), COTIZACION, "Laura")

    assert resultado["decision"] is None
    assert "no está en la cotización" in resultado["aclaracion"]


def test_rechazo_no_crea_una_aprobacion():
    resultado = validar_intencion(Intencion(accion="rechazar"), COTIZACION, "Laura")

    assert resultado["decision"]["aprueba"] is False
    assert resultado["decision"]["aprobado_por"] == "Laura"


def test_intencion_ambigua_pide_aclaracion():
    resultado = validar_intencion(Intencion(accion="aclarar"), COTIZACION, "Laura")

    assert resultado["decision"] is None
    assert resultado["aclaracion"]