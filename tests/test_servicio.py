from grafo.servicio import _revision_recuperable


def test_revision_recuperable_requiere_pedidos_en_lista():
    assert _revision_recuperable({"pedidos": []})
    assert _revision_recuperable({"pedidos": [{"pedido_id": "p1"}]})
    assert not _revision_recuperable({"pedidos": {"pedido_id": "p1"}})
    assert not _revision_recuperable({"pedidos": ["p1"]})
    assert not _revision_recuperable({})
