# Lee de Atlas los productos, ventas y catálogo y los entrega como datos simples. Es lo único que toca la base
import os
from pathlib import Path

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