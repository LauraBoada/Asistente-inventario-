# Nodos del coordinador. Cada nodo llama a las herramientas que exponen los servidores
# MCP (en proceso, como funciones de Python) y nunca toca Mongo directamente: la lectura
# pasa por mcp-inventario, el cálculo por mcp-reposicion y el envío por mcp-pedidos. El
# coordinador no usa LLM: hay_pendientes es la única decisión de flujo y es una comparación
# de números.
from langgraph.types import interrupt

from calculo.abastecimiento import validar_cantidad_personalizada
from mcp_servers.mcp_inventario.server import listar_catalogo_proveedores, listar_productos
from mcp_servers.mcp_pedidos.server import enviar_pedido, registrar_aprobacion_pedido
from mcp_servers.mcp_reposicion.server import revisar_inventario_completo


def leer_inventario(estado):
    """Lee productos y catálogo de proveedores con mcp-inventario (solo lectura)."""
    return {
        "productos": listar_productos(),
        "catalogo": listar_catalogo_proveedores(),
    }


def calcular_reposicion(estado):
    """Calcula los productos críticos, sus opciones de proveedor y la recomendación con
    mcp-reposicion, y deja el estado listo para empezar a revisarlos uno por uno."""
    resultado = revisar_inventario_completo(estado["productos"], estado["catalogo"])
    return {
        "criticos": resultado["criticos"],
        "sin_proveedor": resultado["sin_proveedor"],
        "indice": 0,
        "ciclos": 0,
    }


def hay_pendientes(estado) -> str:
    """Decide si queda un producto crítico por revisar o si ya hay que terminar.

    Compara dos números (cuántos críticos faltan, cuántos ciclos van); es la única
    decisión de flujo del grafo y no necesita LLM.
    """
    queda_alguno = estado["indice"] < len(estado["criticos"])
    dentro_del_limite = estado["ciclos"] < estado["limite_ciclos"]
    return "revisar_siguiente" if queda_alguno and dentro_del_limite else "fin"


def revisar_siguiente(estado):
    """Presenta la cotización del siguiente producto crítico y pausa el grafo hasta que
    el dueño decida (fase 5, bot de Telegram, es quien reanuda con Command(resume=...)).

    Decisión esperada al reanudar: {"aprueba": bool, "proveedor": str opcional (si no
    viene, se usa la recomendada), "aprobado_por": str, "motivo": str opcional si rechaza}.
    """
    critico = estado["criticos"][estado["indice"]]
    decision = interrupt({
        "sku": critico["sku"],
        "titulo_producto": critico["titulo_producto"],
        "opciones": critico["opciones"],
        "recomendada": critico["recomendada"],
    })

    resultado = procesar_decision(critico, decision)

    return {
        "decisiones": estado["decisiones"] + [resultado],
        "indice": estado["indice"] + 1,
        "ciclos": estado["ciclos"] + 1,
    }


def procesar_decision(critico, decision):
    """Aplica la decisión del dueño sobre un producto crítico: si aprueba, registra la
    aprobación y envía el pedido (modo simulado) con mcp-pedidos; si no, queda sin enviar.

    Separada de revisar_siguiente para poder probarla directo, sin pasar por el grafo ni
    por interrupt().
    """
    if not decision.get("aprueba"):
        return {
            "sku": critico["sku"],
            "aprobado": False,
            "estado_envio": None,
            "pedido_id": None,
            "motivo": decision.get("motivo", "El dueño no aprobó el pedido"),
        }

    nombre_proveedor = decision.get("proveedor") or (critico["recomendada"] or {}).get("proveedor")
    opcion = next((o for o in critico["opciones"] if o["proveedor"] == nombre_proveedor), None)
    if opcion is None:
        return {
            "sku": critico["sku"],
            "aprobado": False,
            "estado_envio": None,
            "pedido_id": None,
            "motivo": f"'{nombre_proveedor}' no está entre las opciones de este producto",
        }

    cantidad = decision.get("cantidad", opcion["cantidad_a_pedir"])
    motivo_invalido = validar_cantidad_personalizada(opcion, cantidad)
    if motivo_invalido is not None:
        return {
            "sku": critico["sku"],
            "aprobado": False,
            "estado_envio": None,
            "pedido_id": None,
            "motivo": motivo_invalido,
        }

    total_cop = opcion["total_cop"]
    if cantidad != opcion["cantidad_a_pedir"]:
        total_cop = cantidad * opcion["precio_unitario_cop"]

    aprobacion = registrar_aprobacion_pedido(
        sku=critico["sku"],
        titulo_producto=critico["titulo_producto"],
        proveedor=opcion["proveedor"],
        cantidad=cantidad,
        total_cop=total_cop,
        aprobado_por=decision.get("aprobado_por", "dueño"),
    )
    envio = enviar_pedido(aprobacion["aprobacion_id"])
    return {
        "sku": critico["sku"],
        "aprobado": envio["estado"] in {"simulado_enviado", "enviado"},
        "estado_envio": envio["estado"],
        "pedido_id": envio.get("pedido_id"),
        "motivo": envio.get("motivo"),
    }


def fin(estado):
    """Nodo terminal: no transforma datos, solo marca que el flujo ya cerró."""
    return {"terminado": True}
