import pytest

from calculo.proveedores import crear_cotizacion, leer_cotizacion_chat


def test_crear_cotizacion_valida_y_normaliza_proveedor():
    cotizacion = crear_cotizacion(
        486884,
        "  Distribuidora Norte ",
        12500,
        3,
        12,
        " pedidos@proveedor.com ",
    )

    assert cotizacion == {
        "sku": 486884,
        "proveedor": "Distribuidora Norte",
        "precio_unitario_cop": 12500,
        "plazo_dias": 3,
        "pedido_minimo_unidades": 12,
        "contacto": "pedidos@proveedor.com",
    }


@pytest.mark.parametrize(
    "valores, mensaje",
    [
        ((0, "Proveedor", 100, 2, 1, ""), "SKU"),
        ((1, "", 100, 2, 1, ""), "proveedor"),
        ((1, "Proveedor", 0, 2, 1, ""), "precio"),
        ((1, "Proveedor", 100, 0, 1, ""), "plazo"),
        ((1, "Proveedor", 100, 2, 0, ""), "pedido mínimo"),
        ((1, "Proveedor", 100, 2, 1, "correo-invalido"), "correo"),
    ],
)
def test_rechaza_datos_de_cotizacion_invalidos(valores, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        crear_cotizacion(*valores)


def test_contacto_de_correo_es_opcional():
    fila = crear_cotizacion(1, "Proveedor", 100, 2, 1)

    assert "contacto" not in fila


def test_leer_cotizacion_chat_valida_sku_y_campos():
    cotizacion = leer_cotizacion_chat(
        "486884 | Distribuidora Norte | 12500 | 3 | 12 | pedidos@proveedor.com",
        [486884],
    )

    assert cotizacion == {
        "sku": 486884,
        "proveedor": "Distribuidora Norte",
        "precio_unitario_cop": 12500,
        "plazo_dias": 3,
        "pedido_minimo_unidades": 12,
        "contacto": "pedidos@proveedor.com",
    }


def test_leer_cotizacion_chat_puede_omitir_contacto():
    cotizacion = leer_cotizacion_chat("486884 | Distribuidora Norte | 12500 | 3 | 12", [486884])

    assert "contacto" not in cotizacion


def test_leer_cotizacion_chat_no_acepta_sku_que_no_esta_pendiente():
    with pytest.raises(ValueError, match="pendientes de cotización"):
        leer_cotizacion_chat("1 | Proveedor | 100 | 2 | 1", [486884])
