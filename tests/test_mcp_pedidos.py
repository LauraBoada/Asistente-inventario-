# Prueba mcp-pedidos: rechazo de envíos sin aprobación registrada y envío simulado con
# una aprobación válida. Usa una base de datos falsa en memoria, no se conecta a Atlas.
from bson import ObjectId

import mcp_servers.mcp_pedidos.server as mcp_pedidos
from mcp_servers.mcp_pedidos.server import _validar_aprobacion


class ColeccionFalsa:
    def __init__(self):
        self.documentos = {}

    def insert_one(self, documento):
        id_ = ObjectId()
        self.documentos[id_] = {**documento, "_id": id_}
        return type("Resultado", (), {"inserted_id": id_})()

    def find_one(self, filtro):
        return self.documentos.get(filtro["_id"])

    def update_one(self, filtro, cambios):
        doc = self.documentos.get(filtro["_id"])
        if doc is not None:
            doc.update(cambios["$set"])


class BaseDeDatosFalsa:
    def __init__(self):
        self._colecciones = {}

    def __getitem__(self, nombre):
        return self._colecciones.setdefault(nombre, ColeccionFalsa())


def test_validar_aprobacion_inexistente():
    assert _validar_aprobacion(None) == (False, "No existe una aprobación registrada con ese id")


def test_validar_aprobacion_ya_usada():
    valida, _ = _validar_aprobacion({"usada": True})
    assert valida is False


def test_validar_aprobacion_valida():
    assert _validar_aprobacion({"usada": False}) == (True, "Aprobación válida")


def test_enviar_pedido_rechaza_sin_aprobacion_registrada(monkeypatch):
    monkeypatch.setattr(mcp_pedidos, "_db", BaseDeDatosFalsa())

    resultado = mcp_pedidos.enviar_pedido(str(ObjectId()))

    assert resultado["estado"] == "rechazado"
    assert "aprobación" in resultado["motivo"].lower()


def test_flujo_completo_aprobar_y_enviar_pedido(monkeypatch):
    monkeypatch.setattr(mcp_pedidos, "_db", BaseDeDatosFalsa())

    aprobacion = mcp_pedidos.registrar_aprobacion_pedido(
        sku=12097, proveedor="Distribuidora Andina", cantidad=108,
        total_cop=466560, aprobado_por="dueño",
    )
    envio = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])

    assert envio["estado"] == "simulado_enviado"
    pedido = mcp_pedidos.consultar_pedido(envio["pedido_id"])
    assert pedido["sku"] == 12097
    assert pedido["estado"] == "simulado_enviado"


def test_no_se_puede_usar_dos_veces_la_misma_aprobacion(monkeypatch):
    monkeypatch.setattr(mcp_pedidos, "_db", BaseDeDatosFalsa())

    aprobacion = mcp_pedidos.registrar_aprobacion_pedido(
        sku=1, proveedor="X", cantidad=1, total_cop=1, aprobado_por="dueño",
    )
    primero = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])
    segundo = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])

    assert primero["estado"] == "simulado_enviado"
    assert segundo["estado"] == "rechazado"
