from calculo.revision import revisar_inventario

CATALOGO = {
    1: [
        {"proveedor": "A", "precio_unitario_cop": 100, "plazo_dias": 2, "pedido_minimo_unidades": 12},
        {"proveedor": "B", "precio_unitario_cop": 60, "plazo_dias": 7, "pedido_minimo_unidades": 48},
    ],
}


def producto(sku, stock):
    return {"sku": sku, "titulo_producto": f"Funda {sku}", "demanda_diaria": 2,
            "stock_actual": stock, "pedidos_en_camino": 0, "empaque": 12}


def test_separa_criticos_normales_y_sin_proveedor():
    productos = [producto(1, stock=8),      # crítico, con proveedores
                 producto(2, stock=100),    # stock de sobra: no es crítico
                 producto(3, stock=4)]      # crítico, pero nadie lo surte
    r = revisar_inventario(productos, CATALOGO)

    assert [c["sku"] for c in r["criticos"]] == [1]
    assert r["sin_proveedor"] == [3]
    assert len(r["criticos"][0]["opciones"]) == 2
    assert r["criticos"][0]["recomendada"]["proveedor"] == "A"


def test_los_pedidos_en_camino_cuentan_como_stock():
    p = producto(1, stock=8)
    p["pedidos_en_camino"] = 100          # ya viene mercancía: ya no es crítico
    assert revisar_inventario([p], CATALOGO)["criticos"] == []