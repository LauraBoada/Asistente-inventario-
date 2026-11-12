import sys
from pathlib import Path

# Permite importar las carpetas grafo/ y calculo/ desde scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from grafo.inventario_grafo import construir_grafo

app = construir_grafo(InMemorySaver())
config = {"configurable": {"thread_id": "revision-1"}}

print("Revisando el inventario (puede tardar unos segundos)...")
resultado = app.invoke({"rondas_aclaracion": 0, "resultado": ""}, config)

while "__interrupt__" in resultado:
    info = resultado["__interrupt__"][0].value
    print("\n" + info["mensaje"])
    for p in info["pedidos"]:
        print(f"  - {p['proveedor']}: {p['productos']} productos, total ${p['total_cop']:,} COP")
    if info["sin_proveedor"]:
        print("  Sin proveedor (hay que avisar al dueño):", info["sin_proveedor"])
    respuesta = input("Tu respuesta: ").strip().lower()
    resultado = app.invoke(
        Command(resume={"accion": respuesta, "aprobado_por": "Dueño", "motivo": "Decisión del dueño"}),
        config)

print("\nResultado final:", resultado["resultado"])
for p in resultado.get("pedidos", []):
    print(f"  - {p['proveedor']}: {p.get('estado', '')}")