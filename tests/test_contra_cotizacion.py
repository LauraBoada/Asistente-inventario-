"""Prueba de integración: los datos de Atlas + las funciones deben reproducir
exactamente lo que calculó el notebook (cotizacion.csv)."""
from pathlib import Path

import pandas as pd
import pytest

from calculo.datos import leer_catalogo, leer_productos, obtener_db
from calculo.revision import revisar_inventario

SALIDA = Path(__file__).resolve().parent.parent / "notebooks" / "salida"


def test_coincide_con_la_cotizacion_del_notebook():
    try:
        db = obtener_db()
        productos, catalogo = leer_productos(db), leer_catalogo(db)
    except Exception as error:
        pytest.skip(f"Sin conexión con Atlas: {error}")

    resultado = revisar_inventario(productos, catalogo)
    esperado = pd.read_csv(SALIDA / "cotizacion.csv")
    ref = pd.read_csv(SALIDA / "productos.csv")

    # Mismos productos críticos y mismo producto sin proveedor
    skus_esperados = set(ref[ref["es_critico"] & ref["tiene_proveedor"]]["sku"])
    assert {c["sku"] for c in resultado["criticos"]} == skus_esperados
    assert set(resultado["sin_proveedor"]) == set(ref[ref["es_critico"] & ~ref["tiene_proveedor"]]["sku"])

    # Mismas opciones (cantidad, total, si llega tarde) y misma recomendada
    for c in resultado["criticos"]:
        filas = esperado[esperado["sku"] == c["sku"]].set_index("proveedor")
        for o in c["opciones"]:
            f = filas.loc[o["proveedor"]]
            assert o["cantidad_a_pedir"] == f["cantidad_a_pedir"]
            assert o["total_cop"] == f["total_cop"]
            assert o["llega_tarde"] == bool(f["llega_tarde"])
        assert c["recomendada"]["proveedor"] == filas[filas["recomendado"]].index[0]