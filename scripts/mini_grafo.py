from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class Estado(TypedDict):
    producto: str
    cantidad: int
    decision: str
    resultado: str


def preparar(estado: Estado) -> dict:
    print("1) Preparando el pedido...")
    return {"cantidad": 108}


def esperar_al_dueno(estado: Estado) -> dict:
    # Aquí el grafo SE PAUSA y espera la respuesta del dueño
    respuesta = interrupt(
        {"pregunta": f"¿Apruebas pedir {estado['cantidad']} de {estado['producto']}?"})
    return {"decision": respuesta}


def enviar(estado: Estado) -> dict:
    print("3) Enviando el pedido...")
    return {"resultado": "enviado"}


def cancelar(estado: Estado) -> dict:
    print("3) Cancelando el pedido...")
    return {"resultado": "rechazado"}


def elegir_camino(estado: Estado) -> str:
    return "enviar" if estado["decision"] == "aprobar" else "cancelar"


# Armar el grafo: nodos + flechas + una decisión
grafo = StateGraph(Estado)
grafo.add_node("preparar", preparar)
grafo.add_node("esperar_al_dueno", esperar_al_dueno)
grafo.add_node("enviar", enviar)
grafo.add_node("cancelar", cancelar)

grafo.add_edge(START, "preparar")
grafo.add_edge("preparar", "esperar_al_dueno")
grafo.add_conditional_edges("esperar_al_dueno", elegir_camino,
                            {"enviar": "enviar", "cancelar": "cancelar"})
grafo.add_edge("enviar", END)
grafo.add_edge("cancelar", END)

# El checkpointer es lo que permite pausar y retomar
app = grafo.compile(checkpointer=InMemorySaver())

# El thread_id identifica este pedido para poder retomarlo
config = {"configurable": {"thread_id": "pedido-1"}}

# Primera ejecución: corre hasta la pausa
resultado = app.invoke({"producto": "Funda 12097"}, config)
print("Pregunta al dueño:", resultado["__interrupt__"][0].value["pregunta"])
print("--- el grafo está en pausa, esperando ---")

# Segunda ejecución: el dueño responde y el grafo continúa donde quedó
final = app.invoke(Command(resume="rechazar"), config)
print("Resultado final:", final["resultado"])