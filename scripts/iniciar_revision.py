import sys
from datetime import datetime
from pathlib import Path

# Permite importar las carpetas grafo/ y calculo/ desde scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grafo.inventario_grafo import construir_grafo
from grafo.persistencia import checkpointer_mongodb

# El thread_id es el "número de ticket" de esta revisión
thread_id = datetime.now().strftime("revision-%Y%m%d-%H%M%S")
config = {"configurable": {"thread_id": thread_id}}

with checkpointer_mongodb() as checkpointer:
    app = construir_grafo(checkpointer)
    print("Revisando el inventario (puede tardar unos segundos)...")
    resultado = app.invoke({"rondas_aclaracion": 0, "resultado": ""}, config)

if "__interrupt__" in resultado:
    info = resultado["__interrupt__"][0].value
    print("\n" + info["mensaje"])
    for p in info["pedidos"]:
        print(f"  - {p['proveedor']}: {p['productos']} productos, total ${p['total_cop']:,} COP")
    if info["sin_proveedor"]:
        print("  Sin proveedor (hay que avisar al dueño):", info["sin_proveedor"])
    print("\nEl grafo quedó EN PAUSA y guardado en MongoDB. Ya puedes cerrar este programa.")
    print("Para responder, en cualquier momento:")
    print(f"  python scripts/responder_revision.py {thread_id} aprobar")
else:
    print("Resultado final:", resultado["resultado"])