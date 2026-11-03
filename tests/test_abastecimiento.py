from calculo.abastecimiento import armar_opciones, recomendar

RAPIDO = {"proveedor": "A", "precio_unitario_cop": 100, "plazo_dias": 2, "pedido_minimo_unidades": 12}
LENTO = {"proveedor": "B", "precio_unitario_cop": 60, "plazo_dias": 7, "pedido_minimo_unidades": 48}
MEDIO = {"proveedor": "C", "precio_unitario_cop": 40, "plazo_dias": 3, "pedido_minimo_unidades": 12}


def producto(stock):
    return {"sku": 1, "demanda_diaria": 2, "stock_disponible": stock, "empaque": 12}


def test_armar_opciones_calcula_cantidad_total_y_si_llega_tarde():
    a, b = armar_opciones(producto(stock=8), [RAPIDO, LENTO], dias_cobertura=14)
    # A: 2 x (2 + 14) - 8 = 24 unidades -> 2 empaques; total 24 x 100
    assert (a["cantidad_a_pedir"], a["total_cop"], a["llega_tarde"]) == (24, 2400, False)
    # B: necesita 36, pero su mínimo es 48; total 48 x 60. Con 4 días de stock llega tarde (plazo 7)
    assert (b["cantidad_a_pedir"], b["total_cop"], b["llega_tarde"]) == (48, 2880, True)


def test_recomienda_el_mas_barato_entre_los_que_llegan_a_tiempo():
    # Con 20 unidades alcanzan 10 días: los tres llegan a tiempo.
    # C no es el más rápido, pero es el de menor costo total (24 x 40 = 960)
    opciones = armar_opciones(producto(stock=20), [RAPIDO, LENTO, MEDIO], dias_cobertura=14)
    r = recomendar(opciones)
    assert r["proveedor"] == "C"
    assert r["motivo"] == "Menor costo total entre los que llegan a tiempo"


def test_ninguno_llega_a_tiempo_recomienda_el_mas_rapido():
    # Con 2 unidades solo alcanza 1 día: todos llegan tarde
    opciones = armar_opciones(producto(stock=2), [RAPIDO, LENTO, MEDIO], dias_cobertura=14)
    r = recomendar(opciones)
    assert r["proveedor"] == "A"
    assert r["motivo"] == "Ninguno llega a tiempo: el más rápido"


def test_producto_sin_proveedor():
    assert armar_opciones(producto(stock=8), [], dias_cobertura=14) == []
    assert recomendar([]) is None


def test_demanda_cero_nunca_llega_tarde():
    p = {"sku": 1, "demanda_diaria": 0, "stock_disponible": 5, "empaque": 12}
    assert armar_opciones(p, [LENTO], dias_cobertura=14)[0]["llega_tarde"] is False