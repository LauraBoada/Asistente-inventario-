"""Las dos operaciones que usa el bot: iniciar una revisión y responderla."""
from datetime import datetime, timezone

from langgraph.types import Command

from calculo.datos import obtener_db
from grafo.inventario_grafo import construir_grafo
from grafo.persistencia import checkpointer_mongodb


def _revision_recuperable(info):
    pedidos = info.get("pedidos") if isinstance(info, dict) else None
    return isinstance(pedidos, list) and all(isinstance(pedido, dict) for pedido in pedidos)


def _guardar_revision(thread_id, info, estado="pendiente"):
    db = obtener_db()
    try:
        db["revisiones"].update_one(
            {"_id": thread_id},
            {"$set": {
                "info": info,
                "estado": estado,
                "actualizada_en": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    finally:
        db.client.close()


def listar_revisiones_pendientes():
    db = obtener_db()
    try:
        return [{
            "thread_id": r["_id"],
            **r["info"],
            "actualizada_en": r["actualizada_en"],
            "recuperable": _revision_recuperable(r["info"]),
        } for r in db["revisiones"].find(
            {"estado": "pendiente"},
            {"_id": 1, "info": 1, "actualizada_en": 1},
        ).sort("actualizada_en", -1)]
    finally:
        db.client.close()


def obtener_revision(thread_id):
    db = obtener_db()
    try:
        revision = db["revisiones"].find_one(
            {"_id": thread_id, "estado": "pendiente"},
            {"_id": 1, "info": 1},
        )
        if not revision or not _revision_recuperable(revision["info"]):
            return None
        return {**revision["info"], "thread_id": revision["_id"]}
    finally:
        db.client.close()


def _guardar_datos_interrupcion(thread_id, resultado):
    if "__interrupt__" in resultado:
        _guardar_revision(thread_id, resultado["__interrupt__"][0].value)
        return
    _guardar_revision(thread_id, {}, estado="completada")


def iniciar_revision(thread_id):
    """Corre el grafo hasta la pausa (o hasta el final si no hay nada que pedir)."""
    config = {"configurable": {"thread_id": thread_id}}
    with checkpointer_mongodb() as checkpointer:
        app = construir_grafo(checkpointer)
        resultado = app.invoke({"rondas_aclaracion": 0, "resultado": ""}, config)
    if "__interrupt__" in resultado:
        _guardar_datos_interrupcion(thread_id, resultado)
    return resultado


def responder_revision(thread_id, accion, aprobado_por="Dueño", instruccion="", cotizacion=None):
    """Reanuda la revisión en pausa con la respuesta del dueño."""
    config = {"configurable": {"thread_id": thread_id}}
    with checkpointer_mongodb() as checkpointer:
        app = construir_grafo(checkpointer)
        snapshot = app.get_state(config)
        if not snapshot.next:
            raise ValueError("Esa revisión ya no está en pausa (ya fue respondida).")
        if not _revision_recuperable(snapshot.values):
            raise ValueError(
                "Esta revisión quedó guardada en un formato incompatible. "
                "No la apruebes; inicia una nueva con /revisar."
            )
        respuesta = {
            "accion": accion,
            "aprobado_por": aprobado_por,
            "motivo": "Decisión del dueño",
            "instruccion": instruccion,
            "cotizacion": cotizacion or {},
        }
        resultado = app.invoke(Command(resume=respuesta), config)
    _guardar_datos_interrupcion(thread_id, resultado)
    return resultado