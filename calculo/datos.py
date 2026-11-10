# Lee y escribe en Atlas. Es lo único que toca la base; productos y catálogo son de solo
# lectura, aprobaciones y pedidos son de escritura (los usa mcp-pedidos).
import os
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def obtener_db():
    """Conecta con Atlas y devuelve la base de datos 'inventario'."""
    cliente = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
    return cliente["inventario"]


def leer_productos(db):
    """Lista de productos (sin el campo interno _id de Mongo)."""
    return list(db["productos"].find({}, {"_id": 0}))


def leer_catalogo(db):
    """Catálogo de proveedores agrupado por producto: {sku: [filas]}."""
    catalogo = {}
    for fila in db["catalogo_proveedores"].find({}, {"_id": 0}):
        catalogo.setdefault(fila["sku"], []).append(fila)
    return catalogo


def _a_id(id_texto):
    """Convierte un id de texto a ObjectId; None si no es válido."""
    try:
        return ObjectId(id_texto)
    except (InvalidId, TypeError):
        return None


def registrar_aprobacion(db, aprobacion):
    """Guarda la aprobación del dueño para un pedido y devuelve su id como texto.

    aprobacion: dict con sku, proveedor, cantidad, total_cop y aprobado_por.
    Queda marcada como no usada hasta que mcp-pedidos la consuma al enviar el pedido.
    """
    documento = {**aprobacion, "usada": False, "fecha": datetime.now(timezone.utc)}
    resultado = db["aprobaciones"].insert_one(documento)
    return str(resultado.inserted_id)


def obtener_aprobacion(db, aprobacion_id):
    """Busca una aprobación por id. None si no existe o el id es inválido."""
    oid = _a_id(aprobacion_id)
    if oid is None:
        return None
    return db["aprobaciones"].find_one({"_id": oid})


def marcar_aprobacion_usada(db, aprobacion_id):
    """Marca una aprobación como ya usada, para que no sirva para un segundo envío."""
    db["aprobaciones"].update_one({"_id": _a_id(aprobacion_id)}, {"$set": {"usada": True}})


def registrar_pedido(db, pedido):
    """Guarda un pedido (modo simulado hasta la fase de envío por correo) y devuelve su id."""
    documento = {**pedido, "fecha": datetime.now(timezone.utc)}
    resultado = db["pedidos"].insert_one(documento)
    return str(resultado.inserted_id)


def obtener_pedido(db, pedido_id):
    """Busca un pedido por id. None si no existe o el id es inválido."""
    oid = _a_id(pedido_id)
    if oid is None:
        return None
    return db["pedidos"].find_one({"_id": oid})