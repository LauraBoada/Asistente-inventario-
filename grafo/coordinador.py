# Arma y compila el grafo del coordinador:
#   leer_inventario -> calcular_reposicion -> (¿hay críticos?) -> revisar_siguiente* -> fin
# revisar_siguiente se repite una vez por producto crítico y se pausa en cada uno para la
# aprobación del dueño; el límite de ciclos corta el bucle si algo falla. El checkpoint
# (necesario para que la pausa sobreviva entre llamadas) va en MongoDB en producción y en
# memoria para pruebas y desarrollo local.
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from grafo.estado import EstadoGrafo
from grafo.nodos import calcular_reposicion, fin, hay_pendientes, leer_inventario, revisar_siguiente

_DESTINOS = {"revisar_siguiente": "revisar_siguiente", "fin": "fin"}


def construir_grafo(checkpointer=None):
    """Compila el grafo del coordinador.

    checkpointer: dónde queda el estado mientras el grafo está pausado esperando
    aprobación. Sin uno explícito usa memoria (se pierde al cerrar el proceso); para
    persistirlo en Atlas se le pasa el resultado de construir_checkpointer_mongo().
    """
    grafo = StateGraph(EstadoGrafo)

    grafo.add_node("leer_inventario", leer_inventario)
    grafo.add_node("calcular_reposicion", calcular_reposicion)
    grafo.add_node("revisar_siguiente", revisar_siguiente)
    grafo.add_node("fin", fin)

    grafo.add_edge(START, "leer_inventario")
    grafo.add_edge("leer_inventario", "calcular_reposicion")
    grafo.add_conditional_edges("calcular_reposicion", hay_pendientes, _DESTINOS)
    grafo.add_conditional_edges("revisar_siguiente", hay_pendientes, _DESTINOS)
    grafo.add_edge("fin", END)

    return grafo.compile(checkpointer=checkpointer or MemorySaver())


def construir_checkpointer_mongo():
    """Checkpointer que guarda la pausa del grafo en la misma base 'inventario' de Atlas,
    en vez de en memoria. Requiere MONGODB_URI configurado (ver calculo.datos)."""
    from langgraph.checkpoint.mongodb import MongoDBSaver

    from calculo.datos import obtener_db

    db = obtener_db()
    return MongoDBSaver(
        db.client,
        db_name=db.name,
        checkpoint_collection_name="grafo_checkpoints",
        writes_collection_name="grafo_checkpoint_writes",
    )
