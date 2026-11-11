# Estado que viaja entre los nodos del grafo. El coordinador no usa LLM: solo lee este
# estado y decide el siguiente nodo con funciones simples (si hay críticos, si el dueño
# aprobó, si ya se llegó al límite de ciclos).
from typing import TypedDict


class Cotizacion(TypedDict):
    """Un producto crítico con sus opciones de proveedor (lo que calculó mcp-reposicion)."""

    sku: int
    titulo_producto: str
    opciones: list[dict]
    recomendada: dict | None


class Decision(TypedDict):
    """Qué pasó con un producto crítico después de pasar por la pausa de aprobación."""

    sku: int
    aprobado: bool
    estado_envio: str | None
    pedido_id: str | None
    motivo: str | None


class EstadoGrafo(TypedDict):
    productos: list[dict]
    catalogo: dict
    criticos: list[Cotizacion]
    sin_proveedor: list[int]
    indice: int
    ciclos: int
    limite_ciclos: int
    decisiones: list[Decision]
    terminado: bool


def estado_inicial(limite_ciclos: int = 50) -> EstadoGrafo:
    """Estado con el que arranca el grafo, antes de leer el inventario.

    limite_ciclos es el tope de productos críticos que se revisan en una corrida; evita
    un ciclo sin fin si algo en el flujo falla.
    """
    return {
        "productos": [],
        "catalogo": {},
        "criticos": [],
        "sin_proveedor": [],
        "indice": 0,
        "ciclos": 0,
        "limite_ciclos": limite_ciclos,
        "decisiones": [],
        "terminado": False,
    }
