# Prueba que las herramientas de mcp-reposicion delegan en calculo/ sin cambiar el resultado.
from calculo.abastecimiento import armar_opciones, recomendar
from calculo.reposicion import cantidad_sugerida, es_critico, punto_de_reorden
from calculo.revision import revisar_inventario
from mcp_servers.mcp_reposicion.server import (
    armar_opciones_proveedor,
    calcular_cantidad_sugerida,
    calcular_punto_reorden,
    es_producto_critico,
    recomendar_proveedor,
    revisar_inventario_completo,
)

PRODUCTO = {"sku": 1, "demanda_diaria": 2, "stock_disponible": 10, "empaque": 12}
CATALOGO_PRODUCTO = [
    {"proveedor": "Rapido", "precio_unitario_cop": 100, "plazo_dias": 2, "pedido_minimo_unidades": 12},
    {"proveedor": "Lento", "precio_unitario_cop": 80, "plazo_dias": 20, "pedido_minimo_unidades": 12},
]


def test_calcular_punto_reorden_delega_en_calculo():
    assert calcular_punto_reorden(2, 3, 2) == punto_de_reorden(2, 3, 2)


def test_es_producto_critico_delega_en_calculo():
    assert es_producto_critico(8, 10) == es_critico(8, 10)
    assert es_producto_critico(20, 10) == es_critico(20, 10)


def test_calcular_cantidad_sugerida_delega_en_calculo():
    assert calcular_cantidad_sugerida(2, 3, 14, 8, 12, 12) == cantidad_sugerida(2, 3, 14, 8, 12, 12)


def test_armar_opciones_proveedor_delega_en_calculo():
    assert armar_opciones_proveedor(PRODUCTO, CATALOGO_PRODUCTO, 14) == armar_opciones(PRODUCTO, CATALOGO_PRODUCTO, 14)


def test_recomendar_proveedor_delega_en_calculo():
    opciones = armar_opciones(PRODUCTO, CATALOGO_PRODUCTO, 14)
    assert recomendar_proveedor(opciones) == recomendar(opciones)


def test_recomendar_proveedor_sin_opciones_devuelve_none():
    assert recomendar_proveedor([]) is None


def test_revisar_inventario_completo_delega_en_calculo():
    productos = [
        {"sku": 1, "titulo_producto": "A", "demanda_diaria": 2, "stock_actual": 0,
         "pedidos_en_camino": 0, "empaque": 12},
        {"sku": 2, "titulo_producto": "B", "demanda_diaria": 1, "stock_actual": 1000,
         "pedidos_en_camino": 0, "empaque": 6},
    ]
    catalogo = {1: CATALOGO_PRODUCTO}
    esperado = revisar_inventario(productos, catalogo)
    assert revisar_inventario_completo(productos, catalogo) == esperado
    assert {c["sku"] for c in esperado["criticos"]} == {1}
