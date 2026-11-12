import sys
from pathlib import Path

# Permite importar las carpetas grafo/ y calculo/ desde scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.types import Command

from grafo.inventario_grafo import construir_grafo
from grafo.persistencia import checkpointer_mongodb

if len(sys.argv) != 3:
    print("Uso: python scripts/responder_revision.py THREAD_ID aprobar|rechazar|pendiente")
    sys.exit(1)

thread_id, respuesta = sys.argv[1], sys.argv[2].strip().lower()
config = {"configurable": {"thread_id": thread_id}}

with checkpointer_mongodb() as checkpointer:
    app = construir_grafo(checkpointer)

    # ¿Existe una revisión en pausa con ese número de ticket?
    if not app.get_state(config).next:
        print("No hay ninguna revisión en pausa con ese identificador (o ya terminó).")
        sys.exit(1)

    resultado = app.invoke(
        Command(resume={"accion": respuesta, "aprobado_por": "Dueño", "motivo": "Decisión del dueño"}),
        config)

if "__interrupt__" in resultado:
    info = resultado["__interrupt__"][0].value
    print(info["mensaje"])
    print(f"Vuelve a responder: python scripts/responder_revision.py {thread_id} aprobar")
else:
    print("Resultado final:", resultado["resultado"])
    for p in resultado.get("pedidos", []):
        print(f"  - {p['proveedor']}: {p.get('estado', '')}")