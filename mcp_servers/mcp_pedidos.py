import sys
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

# Permite importar la carpeta calculo/ aunque el servidor se lance desde otro lugar
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId
from bson.errors import InvalidId
from mcp.server.fastmcp import FastMCP

from calculo import pedidos as reglas
from calculo.correo import preparar_correo, resolver_destinatario
from calculo.datos import obtener_db

mcp = FastMCP("pedidos")
db = obtener_db()


# ---------- Ayudas internas (no son herramientas) ----------

def _leer(pedido_id, session=None):
    try:
        documento = db["pedidos"].find_one({"_id": ObjectId(pedido_id)}, session=session)
    except (InvalidId, TypeError) as error:
        raise reglas.ErrorDePedido(f"El identificador '{pedido_id}' no es válido") from error
    if documento is None:
        raise reglas.ErrorDePedido(f"No existe el pedido {pedido_id}")
    return documento


def _guardar(nuevo, estado_anterior, session=None):
    """Guarda el pedido solo si nadie lo cambió mientras tanto."""
    resultado = db["pedidos"].replace_one(
        {"_id": nuevo["_id"], "estado": estado_anterior}, nuevo, session=session)
    if resultado.matched_count == 0:
        raise reglas.ErrorDePedido("El pedido cambió mientras se procesaba; inténtalo de nuevo")


def _salida(documento):
    """Convierte el pedido a algo que se pueda enviar por MCP (texto y números)."""
    salida = {k: v for k, v in documento.items() if k != "_id"}
    salida["pedido_id"] = str(documento["_id"])
    for campo, valor in salida.items():
        if isinstance(valor, datetime):
            salida[campo] = valor.isoformat()
    return salida


def _bitacora(nodo, evento, detalle="", session=None):
    db["bitacora"].insert_one({
        "fecha": datetime.now(timezone.utc), "nodo": nodo,
        "evento": evento, "detalle": detalle}, session=session)


def _enviar_por_correo(pedido):
    """Simula el correo por defecto; Gmail requiere activación y credenciales explícitas."""
    modo = os.environ.get("MODO_ENVIO", "simulado").strip().lower()
    proveedor = db["proveedores"].find_one(
        {"proveedor": pedido["proveedor"]}, {"_id": 0, "contacto": 1})
    contacto_proveedor = proveedor.get("contacto") if proveedor else None
    destinatario = resolver_destinatario(
        contacto_proveedor,
        modo,
        os.environ.get("GMAIL_TEST_RECIPIENT"),
    )
    correo = preparar_correo(pedido, destinatario)
    if modo == "simulado":
        return {"canal": "simulado", **correo}
    if modo != "gmail":
        raise reglas.ErrorDePedido("MODO_ENVIO debe ser 'simulado' o 'gmail'.")
    if not destinatario or destinatario.endswith(".example"):
        raise reglas.ErrorDePedido(
            "No hay destinatario real: configura GMAIL_TEST_RECIPIENT para las pruebas "
            "o un contacto válido para el proveedor en MongoDB.")

    usuario = os.environ.get("GMAIL_USER")
    clave = os.environ.get("GMAIL_APP_PASSWORD")
    if not usuario or not clave:
        raise reglas.ErrorDePedido(
            "Para enviar por Gmail configura GMAIL_USER y GMAIL_APP_PASSWORD en .env.")

    mensaje = EmailMessage()
    mensaje["From"] = usuario
    mensaje["To"] = destinatario
    mensaje["Subject"] = correo["asunto"]
    mensaje.set_content(correo["cuerpo"])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
        servidor.login(usuario, clave)
        servidor.send_message(mensaje)
    return {"canal": "gmail", "destinatario": destinatario, "asunto": correo["asunto"]}


# ---------- Herramientas ----------

@mcp.tool()
def crear_borrador(proveedor: str, items: list[dict]) -> dict:
    """Crea un pedido en estado borrador para un proveedor.
    items: lista con sku, cantidad y precio_unitario_cop de cada producto."""
    pedido = reglas.crear_borrador(proveedor, items)
    pedido["_id"] = db["pedidos"].insert_one(pedido).inserted_id
    _bitacora("crear_borrador", "borrador_creado", f"{proveedor}: total {pedido['total_cop']}")
    return _salida(pedido)


@mcp.tool()
def solicitar_aprobacion(pedido_id: str) -> dict:
    """Deja el borrador esperando la respuesta del dueño."""
    pedido = _leer(pedido_id)
    nuevo = reglas.pedir_aprobacion(pedido)
    _guardar(nuevo, pedido["estado"])
    _bitacora("solicitar_aprobacion", "esperando_aprobacion", pedido_id)
    return _salida(nuevo)


@mcp.tool()
def registrar_aprobacion(pedido_id: str, aprobado_por: str,
                         confirmacion_reforzada: bool = False,
                         umbral_alto_valor: int | None = None) -> dict:
    """Registra quién aprobó el pedido y cuándo. Si el pedido supera el umbral
    de alto valor, exige confirmacion_reforzada."""
    pedido = _leer(pedido_id)
    nuevo = reglas.aprobar(pedido, aprobado_por, confirmacion_reforzada, umbral_alto_valor)
    _guardar(nuevo, pedido["estado"])
    _bitacora("registrar_aprobacion", "pedido_aprobado", f"{pedido_id} por {aprobado_por}")
    return _salida(nuevo)


@mcp.tool()
def rechazar_pedido(pedido_id: str, motivo: str = "") -> dict:
    """Marca el pedido como rechazado por el dueño. Un pedido rechazado nunca se envía."""
    pedido = _leer(pedido_id)
    nuevo = reglas.rechazar(pedido, motivo)
    _guardar(nuevo, pedido["estado"])
    _bitacora("rechazar_pedido", "pedido_rechazado", f"{pedido_id}: {motivo}")
    return _salida(nuevo)


@mcp.tool()
def reemplazar_pedidos(pedidos_actuales: list[str], nuevos: list[dict]) -> list[dict]:
    """Reemplaza borradores pendientes por los productos seleccionados, en una transacción."""
    with db.client.start_session() as session:
        with session.start_transaction():
            actuales = [_leer(pedido_id, session) for pedido_id in pedidos_actuales]
            for pedido in actuales:
                if pedido["estado"] != reglas.ESPERANDO:
                    raise reglas.ErrorDePedido(
                        f"No se puede reemplazar un pedido en estado '{pedido['estado']}'")

            creados = []
            for pedido in actuales:
                nuevo = reglas.rechazar(pedido, "Reemplazado por la selección del dueño")
                _guardar(nuevo, pedido["estado"], session)
                _bitacora("reemplazar_pedidos", "pedido_reemplazado",
                          str(pedido["_id"]), session)

            for grupo in nuevos:
                borrador = reglas.crear_borrador(grupo["proveedor"], grupo["items"])
                borrador["_id"] = db["pedidos"].insert_one(
                    borrador, session=session).inserted_id
                esperando = reglas.pedir_aprobacion(borrador)
                _guardar(esperando, borrador["estado"], session)
                _bitacora("reemplazar_pedidos", "pedido_creado",
                          f"{grupo['proveedor']}: total {esperando['total_cop']}", session)
                creados.append(_salida(esperando))
    return [{
        "pedido_id": pedido["pedido_id"],
        "proveedor": pedido["proveedor"],
        "productos": len(pedido["items"]),
        "total_cop": pedido["total_cop"],
    } for pedido in creados]


@mcp.tool()
def enviar_pedido(pedido_id: str) -> dict:
    """Simula por defecto el correo; Gmail real requiere MODO_ENVIO=gmail."""
    pedido = _leer(pedido_id)
    anterior = pedido["estado"]
    reglas.marcar_enviado(pedido)  # Valida aprobación y evita un segundo envío real.
    modo = os.environ.get("MODO_ENVIO", "simulado").strip().lower()
    if modo not in ("simulado", "gmail"):
        raise reglas.ErrorDePedido("MODO_ENVIO debe ser 'simulado' o 'gmail'.")
    try:
        confirmacion = _enviar_por_correo(pedido)
    except reglas.ErrorDePedido:
        raise
    except Exception as error:
        if modo == "simulado":
            raise
        fallido = reglas.marcar_fallido(pedido, str(error))
        _guardar(fallido, anterior)
        _bitacora("enviar_pedido", "envio_fallido", f"{pedido_id}: {error}")
        raise reglas.ErrorDePedido(f"No se pudo enviar el pedido: {error}")
    if confirmacion["canal"] == "simulado":
        simulacion = {**pedido, "ultima_simulacion": confirmacion}
        _guardar(simulacion, anterior)
        _bitacora("enviar_pedido", "envio_simulado",
                  f"{pedido_id} a {confirmacion['destinatario']}")
        return _salida({**simulacion, "estado": "simulado", "correo": confirmacion})

    enviado = reglas.marcar_enviado(pedido)
    _guardar(enviado, anterior)
    _bitacora("enviar_pedido", "pedido_enviado",
              f"{pedido_id} ({confirmacion['canal']}) a {confirmacion['destinatario']}")
    return _salida({**enviado, "correo": confirmacion})

@mcp.tool()
def dejar_pendiente(pedido_id: str) -> dict:
    """El dueño no respondió a tiempo: el pedido queda pendiente y no se envía."""
    pedido = _leer(pedido_id)
    nuevo = reglas.marcar_pendiente(pedido)
    _guardar(nuevo, pedido["estado"])
    _bitacora("dejar_pendiente", "pedido_pendiente", pedido_id)
    return _salida(nuevo)

@mcp.tool()
def registrar_bitacora(nodo: str, evento: str, detalle: str = "") -> str:
    """Agrega una línea a la bitácora de auditoría (solo agrega, nunca borra)."""
    _bitacora(nodo, evento, detalle)
    return "registrado"


if __name__ == "__main__":
    mcp.run()