import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")
SALIDA = RAIZ / "notebooks" / "salida"

# 1. Conectar y probar la conexión
cliente = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000)
cliente.admin.command("ping")
print("Conexión con Atlas: OK")
db = cliente["inventario"]

# 2. Cada CSV pasa a ser una colección
archivos = {
    "productos": "productos.csv",
    "ventas": "ventas_diarias.csv",
    "proveedores": "proveedores.csv",
    "catalogo_proveedores": "catalogo_proveedores.csv",
}
for coleccion, archivo in archivos.items():
    df = pd.read_csv(SALIDA / archivo)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    registros = df.astype(object).where(df.notna(), None).to_dict("records")
    db[coleccion].delete_many({})        # vacía antes de cargar: se puede correr varias veces sin duplicar
    db[coleccion].insert_many(registros)
    print(f"{coleccion:<22} {len(registros):>5} documentos")

# 3. Índices: hacen las consultas por producto y fecha rápidas
db["productos"].create_index("sku", unique=True)
db["ventas"].create_index([("sku", 1), ("fecha", 1)])
db["catalogo_proveedores"].create_index("sku")
print("Índices creados")