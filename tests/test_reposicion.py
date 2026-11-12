#Pruebas de que la fórmula da lo correcto
import pytest

from calculo.reposicion import punto_de_reorden, es_critico, cantidad_sugerida


def test_ejemplo_de_la_guia():
    demanda = 2
    assert punto_de_reorden(demanda, plazo=3, dias_seguridad=2) == 10
    assert es_critico(stock_disponible=8, punto_reorden=10) is True
    assert cantidad_sugerida(
        demanda=2, plazo=3, dias_cobertura=14,
        stock_disponible=8, empaque=12, pedido_minimo=12,
    ) == 36


def test_stock_cero():
    # Sin stock: 2 x (3 + 14) = 34 unidades -> 3 empaques de 12 = 36
    assert es_critico(stock_disponible=0, punto_reorden=10) is True
    assert cantidad_sugerida(2, 3, 14, 0, 12, 12) == 36


def test_pedido_minimo_mayor_que_lo_calculado():
    # Se necesitan 6, pero el proveedor exige mínimo 48
    assert cantidad_sugerida(1, 2, 14, 10, 6, 48) == 48


def test_pedido_minimo_no_multiplo_del_empaque_se_redondea_hacia_arriba():
    # El proveedor exige 10, pero solo se vende en empaques de 6
    assert cantidad_sugerida(1, 1, 1, 0, 6, 10) == 12


def test_stock_que_ya_alcanza_no_pide_nada():
    # Necesidad = 34 - 40 = -6, no hay que pedir
    assert cantidad_sugerida(2, 3, 14, 40, 12, 12) == 0


def test_cantidad_exacta_no_suma_un_empaque_de_mas():
    # Necesidad = 34 - 10 = 24 = justo 2 empaques de 12
    assert cantidad_sugerida(2, 3, 14, 10, 12, 12) == 24


def test_decimales_no_suman_un_empaque_de_mas():
    # 1.1 x 17 - 6.7 debería ser 12, pero la computadora lo guarda como 12.000000000000004
    assert cantidad_sugerida(1.1, 3, 14, 6.7, 12, 12) == 12


def test_demanda_cero_no_es_critica_si_hay_stock():
    assert es_critico(stock_disponible=5, punto_reorden=punto_de_reorden(0, 3, 2)) is False
    assert cantidad_sugerida(0, 3, 14, 5, 12, 12) == 0


def test_empaque_invalido():
    with pytest.raises(ValueError):
        cantidad_sugerida(2, 3, 14, 8, 0, 12)