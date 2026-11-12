import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@contextmanager
def checkpointer_mongodb():
    """Guarda la 'partida' del grafo en MongoDB (base 'inventario'),
    para poder pausarla y retomarla aunque el programa se cierre."""
    with MongoDBSaver.from_conn_string(
        os.environ["MONGODB_URI"], os.environ.get("MONGODB_DB", "inventario")
    ) as checkpointer:
        if hasattr(checkpointer, "setup"):
            checkpointer.setup()
        yield checkpointer