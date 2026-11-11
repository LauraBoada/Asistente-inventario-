# Prueba mcp-inventario: solo lectura, delega en calculo.datos. Usa una base de datos
# falsa en memoria, no se conecta a Atlas.
import mcp_servers.mcp_inventario.server as mcp_inventario


class ColeccionFalsa:
    def __init__(self, documentos):
        self._documentos = documentos

    def find(self, filtro=None, proyeccion=None):
        return list(self._documentos)


class BaseDeDatosFalsa:
    def __init__(self, productos, catalogo_proveedores):
        self._colecciones = {
            "productos": ColeccionFalsa(productos),
            "catalogo_proveedores": ColeccionFalsa(catalogo_proveedores),
        }

    def __getitem__(self, nombre):
        return self._colecciones[nombre]


PRODUCTOS = [
    {"sku": 1, "titulo_producto": "Funda A", "demanda_diaria": 2, "stock_actual": 10, "empaque": 12},
    {"sku": 2, "titulo_producto": "Funda B", "demanda_diaria": 1, "stock_actual": 5, "empaque": 6},
]
CATALOGO = [
    {"sku": 1, "proveedor": "Distribuidora Andina", "precio_unitario_cop": 100, "plazo_dias": 2, "pedido_minimo_unidades": 12},
]


def _preparar(monkeypatch):
    monkeypatch.setattr(mcp_inventario, "_db", BaseDeDatosFalsa(PRODUCTOS, CATALOGO))


def test_listar_productos(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.listar_productos() == PRODUCTOS


def test_obtener_producto_existente(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.obtener_producto(2) == PRODUCTOS[1]


def test_obtener_producto_inexistente(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.obtener_producto(999) is None


def test_obtener_catalogo_proveedores_con_proveedor(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.obtener_catalogo_proveedores(1) == CATALOGO


def test_obtener_catalogo_proveedores_sin_proveedor(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.obtener_catalogo_proveedores(2) == []


def test_listar_catalogo_proveedores(monkeypatch):
    _preparar(monkeypatch)
    assert mcp_inventario.listar_catalogo_proveedores() == {1: CATALOGO}
