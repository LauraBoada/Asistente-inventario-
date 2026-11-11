# Prueba mcp-pedidos: rechazo de envíos sin aprobación registrada y envío simulado con
# una aprobación válida. Usa una base de datos falsa en memoria, no se conecta a Atlas.
import smtplib

from bson import ObjectId
import pytest

import mcp_servers.mcp_pedidos.correo as correo
import mcp_servers.mcp_pedidos.server as mcp_pedidos
from mcp_servers.mcp_pedidos.server import _validar_aprobacion


@pytest.fixture(autouse=True)
def modo_simulado_por_defecto(monkeypatch):
    monkeypatch.setenv("MODO_ENVIO_PEDIDOS", "simulado")


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
        if doc is None or ("usada" in filtro and doc.get("usada") != filtro["usada"]):
            return type("Resultado", (), {"modified_count": 0})()
        valores = cambios["$set"]
        modificado = any(doc.get(clave) != valor for clave, valor in valores.items())
        doc.update(valores)
        return type("Resultado", (), {"modified_count": int(modificado)})()


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


def test_envio_gmail_usa_destinatario_configurado_y_actualiza_estado(monkeypatch):
    monkeypatch.setattr(mcp_pedidos, "_db", BaseDeDatosFalsa())
    monkeypatch.setenv("MODO_ENVIO_PEDIDOS", "gmail")
    monkeypatch.setenv("GMAIL_USER", "tienda@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_DESTINATARIOS", '{"Distribuidora Andina":"andina@example.com"}')
    capturado = {}

    def enviar(preparacion):
        capturado["destinatario"] = preparacion["destinatario"]
        return {"estado": "enviado", "destinatario": preparacion["destinatario"]}

    monkeypatch.setattr(mcp_pedidos, "ejecutar_envio", enviar)
    aprobacion = mcp_pedidos.registrar_aprobacion_pedido(
        sku=12097, proveedor="Distribuidora Andina", cantidad=12,
        total_cop=1200, aprobado_por="dueño",
    )

    resultado = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])
    pedido = mcp_pedidos.consultar_pedido(resultado["pedido_id"])

    assert resultado["estado"] == "enviado"
    assert capturado["destinatario"] == "andina@example.com"
    assert pedido["estado"] == "enviado"
    assert pedido["correo_destino"] == "andina@example.com"


def test_falta_de_correo_del_proveedor_no_consumo_aprobacion(monkeypatch):
    db = BaseDeDatosFalsa()
    monkeypatch.setattr(mcp_pedidos, "_db", db)
    monkeypatch.setenv("MODO_ENVIO_PEDIDOS", "gmail")
    monkeypatch.setenv("GMAIL_USER", "tienda@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_DESTINATARIOS", "{}")
    aprobacion = mcp_pedidos.registrar_aprobacion_pedido(
        sku=1, proveedor="Proveedor sin correo", cantidad=12,
        total_cop=1200, aprobado_por="dueño",
    )

    resultado = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])
    aprobacion_guardada = db["aprobaciones"].find_one({"_id": ObjectId(aprobacion["aprobacion_id"])})

    assert resultado["estado"] == "rechazado"
    assert aprobacion_guardada["usada"] is False


def test_ejecutar_envio_conecta_a_gmail_sin_red_real(monkeypatch):
    class ServidorSmtpFalso:
        def __init__(self):
            self.mensaje = None
            self.credenciales = None

        def __enter__(self):
            return self

        def __exit__(self, tipo, valor, traza):
            return False

        def login(self, remitente, clave):
            self.credenciales = (remitente, clave)

        def send_message(self, mensaje):
            self.mensaje = mensaje
            return {}

    servidor = ServidorSmtpFalso()
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", lambda *args, **kwargs: servidor)
    monkeypatch.setenv("MODO_ENVIO_PEDIDOS", "gmail")
    monkeypatch.setenv("GMAIL_USER", "tienda@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app password")
    monkeypatch.setenv("GMAIL_DESTINATARIOS", '{"Andina":"proveedor@example.com"}')

    preparacion = correo.preparar_envio({
        "sku": 42,
        "titulo_producto": "Funda protectora",
        "proveedor": "Andina",
        "cantidad": 12,
        "total_cop": 1200,
    })
    resultado = correo.ejecutar_envio(preparacion)

    assert resultado == {"estado": "enviado", "destinatario": "proveedor@example.com"}
    assert servidor.credenciales == ("tienda@example.com", "apppassword")
    assert servidor.mensaje["To"] == "proveedor@example.com"
    assert "Funda protectora" in servidor.mensaje.get_content()
    assert "12 unidades" in servidor.mensaje.get_content()


def test_fallo_de_gmail_guarda_error_y_consumo_aprobacion(monkeypatch):
    db = BaseDeDatosFalsa()
    monkeypatch.setattr(mcp_pedidos, "_db", db)
    monkeypatch.setenv("MODO_ENVIO_PEDIDOS", "gmail")
    monkeypatch.setenv("GMAIL_USER", "tienda@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("GMAIL_DESTINATARIOS", '{"Andina":"proveedor@example.com"}')
    monkeypatch.setattr(mcp_pedidos, "ejecutar_envio", lambda preparacion: (_ for _ in ()).throw(smtplib.SMTPException("fallo")))
    aprobacion = mcp_pedidos.registrar_aprobacion_pedido(
        sku=42, proveedor="Andina", cantidad=12, total_cop=1200, aprobado_por="dueño",
    )

    resultado = mcp_pedidos.enviar_pedido(aprobacion["aprobacion_id"])
    pedido = mcp_pedidos.consultar_pedido(resultado["pedido_id"])

    assert resultado["estado"] == "envio_fallido"
    assert pedido["estado"] == "envio_fallido"
    assert "consumida" in resultado["motivo"]
