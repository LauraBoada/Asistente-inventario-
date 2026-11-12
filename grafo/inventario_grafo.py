import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from calculo.gemini import ErrorDeInterpretacion, seleccionar_productos
from grafo.clientes_mcp import llamar, llamar_lista, servidor

MAX_ACLARACIONES = 2


class Estado(TypedDict):
    criticos: list           # productos a reponer, con sus opciones y la recomendada
    sin_proveedor: list      # críticos que ningún proveedor surte
    pedidos: list            # un pedido por proveedor
    decision: dict           # respuesta del dueño: {"accion": ..., "aprobado_por": ...}
    rondas_aclaracion: int
    resultado: str
    mensaje_revision: str


# ---------------- Nodos ----------------

def revisar(estado: Estado) -> dict:
    """Lee el inventario (mcp-inventario) y calcula qué reponer (mcp-reposicion)."""
    async def tarea():
        async with servidor("mcp_inventario.py") as inventario:
            productos = await llamar_lista(inventario, "consultar_inventario")
            catalogo = await llamar_lista(inventario, "catalogo_proveedores")
        async with servidor("mcp_reposicion.py") as reposicion:
            return await llamar(reposicion, "revisar_inventario",
                                {"productos": productos, "catalogo": catalogo})

    revision = asyncio.run(tarea())
    return {"criticos": revision["criticos"], "sin_proveedor": revision["sin_proveedor"],
            "rondas_aclaracion": 0, "resultado": ""}


def armar_pedidos(estado: Estado) -> dict:
    """Agrupa lo recomendado por proveedor y crea un borrador por cada uno (mcp-pedidos)."""
    por_proveedor = _agrupar_por_proveedor(estado["criticos"], "recomendada")

    async def tarea():
        pedidos = []
        async with servidor("mcp_pedidos.py") as pedidos_mcp:
            for proveedor, items in por_proveedor.items():
                borrador = await llamar(pedidos_mcp, "crear_borrador",
                                        {"proveedor": proveedor, "items": items})
                pedido = await llamar(pedidos_mcp, "solicitar_aprobacion",
                                      {"pedido_id": borrador["pedido_id"]})
                pedidos.append({"pedido_id": pedido["pedido_id"], "proveedor": proveedor,
                                "productos": len(items), "total_cop": pedido["total_cop"]})
        return pedidos

    return {"pedidos": asyncio.run(tarea())}


def _agrupar_por_proveedor(criticos, campo_opcion):
    por_proveedor = {}
    for critico in criticos:
        opcion = critico[campo_opcion]
        por_proveedor.setdefault(opcion["proveedor"], []).append({
            "sku": critico["sku"],
            "cantidad": opcion["cantidad_a_pedir"],
            "precio_unitario_cop": opcion["precio_unitario_cop"],
        })
    return por_proveedor


def _resumen_productos(criticos):
    resumen = []
    for producto in criticos:
        recomendada = producto["recomendada"]
        hubo_seleccion = "seleccionada" in producto
        seleccionada = producto.get("seleccionada", recomendada)
        opciones = []
        for opcion in producto["opciones"]:
            recomendada_para_producto = opcion["proveedor"] == recomendada["proveedor"]
            seleccionada_para_producto = (
                hubo_seleccion and opcion["proveedor"] == seleccionada["proveedor"]
            )
            opciones.append({
                "proveedor": opcion["proveedor"],
                "cantidad": (seleccionada["cantidad_a_pedir"] if seleccionada_para_producto
                             else opcion["cantidad_a_pedir"]),
                "total_cop": (seleccionada["total_cop"] if seleccionada_para_producto
                              else opcion["total_cop"]),
                "plazo_dias": opcion["plazo_dias"],
                "llega_tarde": opcion["llega_tarde"],
                "empaque": opcion["empaque"],
                "pedido_minimo_unidades": opcion["pedido_minimo_unidades"],
                "recomendada": recomendada_para_producto,
                "seleccionada": seleccionada_para_producto,
            })
        resumen.append({
            "sku": producto["sku"],
            "titulo": producto["titulo_producto"],
            "recomendada": recomendada["proveedor"],
            "seleccionada": seleccionada["proveedor"] if hubo_seleccion else None,
            "opciones": opciones,
        })
    return resumen


def esperar_dueno(estado: Estado) -> dict:
    """PAUSA: el grafo se detiene hasta que el dueño responda. Sin efectos secundarios,
    porque este nodo se vuelve a ejecutar desde el inicio al reanudar."""
    mensaje = estado.get("mensaje_revision") or "Pedidos listos. Puedes aprobar, rechazar, dejar pendiente o ajustar la selección."
    if estado["rondas_aclaracion"] > 0 and not estado.get("mensaje_revision"):
        mensaje = "No entendí tu respuesta. Responde solo: aprobar, rechazar o pendiente."
    # Resumen de cada producto con todas sus opciones, para mostrárselo al dueño.
    criticos = _resumen_productos(estado["criticos"])
    respuesta = interrupt({"mensaje": mensaje, "criticos": criticos, "pedidos": estado["pedidos"],
                           "sin_proveedor": estado["sin_proveedor"]})
    return {"decision": respuesta}


def interpretar(estado: Estado) -> dict:
    """Revisa que la respuesta sea válida. Lo que no se entiende se marca como ambiguo."""
    decision = estado["decision"] if isinstance(estado["decision"], dict) else {}
    accion = decision.get("accion")
    if accion not in ("aprobar", "rechazar", "pendiente", "ajustar", "agregar_cotizacion"):
        accion = "ambiguo"
    return {"decision": {**decision, "accion": accion}, "mensaje_revision": ""}


def ajustar_pedido(estado: Estado) -> dict:
    """Interpreta una selección con Gemini y reemplaza los borradores aún no aprobados."""
    try:
        seleccion, ajustes = seleccionar_productos(
            estado["decision"].get("instruccion", ""),
            estado["criticos"],
        )
        por_proveedor = _agrupar_por_proveedor(seleccion, "seleccionada")

        nuevos = [{"proveedor": proveedor, "items": items}
                  for proveedor, items in por_proveedor.items()]

        async def tarea():
            async with servidor("mcp_pedidos.py") as pedidos_mcp:
                return await llamar_lista(pedidos_mcp, "reemplazar_pedidos", {
                    "pedidos_actuales": [p["pedido_id"] for p in estado["pedidos"]],
                    "nuevos": nuevos,
                })

        pedidos = asyncio.run(tarea())
    except (ErrorDeInterpretacion, RuntimeError) as error:
        return {
            "decision": {},
            "mensaje_revision": f"No pude ajustar la selección: {error}",
            "rondas_aclaracion": 0,
        }

    mensaje = (
        f"Confirmación de tu selección: {len(seleccion)} producto(s), "
        "con los proveedores y cantidades que pediste (ajustados al empaque o mínimo si aplica). "
        "Revisa las opciones y el total; todavía no se ha enviado nada."
    )
    if ajustes:
        mensaje += " " + " ".join(ajustes)
    return {
        "criticos": seleccion,
        "pedidos": pedidos,
        "decision": {},
        "mensaje_revision": mensaje,
        "rondas_aclaracion": 0,
    }


def agregar_cotizacion(estado: Estado) -> dict:
    """Guarda la cotización recibida por Telegram y actualiza la revisión pausada."""
    solicitud = estado["decision"].get("cotizacion", {})
    sku = solicitud.get("sku")
    if sku not in estado.get("sin_proveedor", []):
        return {
            "decision": {},
            "mensaje_revision": "Ese SKU no está en la lista de productos pendientes de cotización.",
            "rondas_aclaracion": 0,
        }
    try:
        async def tarea():
            async with servidor("mcp_inventario.py") as inventario:
                await llamar(inventario, "agregar_cotizacion", solicitud)
                productos = await llamar_lista(inventario, "consultar_inventario")
                catalogo = await llamar_lista(inventario, "catalogo_proveedores")
            async with servidor("mcp_reposicion.py") as reposicion:
                return await llamar(reposicion, "revisar_inventario", {
                    "productos": productos,
                    "catalogo": catalogo,
                })

        revision = asyncio.run(tarea())
        criticos = revision["criticos"]
        sin_proveedor = revision["sin_proveedor"]
        grupos = [
            {"proveedor": proveedor, "items": items}
            for proveedor, items in _agrupar_por_proveedor(criticos, "recomendada").items()
        ]

        async def reemplazar():
            async with servidor("mcp_pedidos.py") as pedidos_mcp:
                return await llamar_lista(pedidos_mcp, "reemplazar_pedidos", {
                    "pedidos_actuales": [p["pedido_id"] for p in estado["pedidos"]],
                    "nuevos": grupos,
                })

        pedidos = asyncio.run(reemplazar())
    except (RuntimeError, ValueError, KeyError) as error:
        return {
            "decision": {},
            "mensaje_revision": f"No pude guardar o recalcular la cotización: {error}",
            "rondas_aclaracion": 0,
        }

    return {
        "criticos": criticos,
        "sin_proveedor": sin_proveedor,
        "pedidos": pedidos,
        "decision": {},
        "mensaje_revision": (
            f"✅ Cotización guardada para el SKU {sku}. "
            "Actualicé el cálculo de inventario y los pedidos. Revisa antes de decidir."
        ),
        "resultado": "sin_novedades" if not criticos and not sin_proveedor else "",
        "rondas_aclaracion": 0,
    }


def posponer(estado: Estado) -> dict:
    """Mantiene la revisión abierta para que el dueño pueda retomarla después."""
    return {
        "decision": {},
        "mensaje_revision": "⏳ La revisión sigue guardada en MongoDB. Puedes retomarla con /pendientes.",
    }


def pedir_aclaracion(estado: Estado) -> dict:
    return {"rondas_aclaracion": estado["rondas_aclaracion"] + 1}


def enviar_pedidos(estado: Estado) -> dict:
    """Registra la aprobación y envía cada pedido (el servidor se niega si algo no cumple)."""
    quien = estado["decision"].get("aprobado_por") or "Dueño"

    async def tarea():
        resultados = []
        async with servidor("mcp_pedidos.py") as pedidos_mcp:
            for pedido in estado["pedidos"]:
                try:
                    await llamar(pedidos_mcp, "registrar_aprobacion",
                                 {"pedido_id": pedido["pedido_id"], "aprobado_por": quien})
                    enviado = await llamar(pedidos_mcp, "enviar_pedido",
                                           {"pedido_id": pedido["pedido_id"]})
                    resultados.append({
                        **pedido,
                        "estado": enviado["estado"],
                        "correo": enviado.get("correo"),
                    })
                except RuntimeError as error:
                    resultados.append({
                        **pedido,
                        "estado": "error",
                        "detalle": " ".join(str(error).split())[:500],
                    })
        return resultados

    resultados = asyncio.run(tarea())
    todos = all(r["estado"] == "enviado" for r in resultados)
    todos_simulados = bool(resultados) and all(r["estado"] == "simulado" for r in resultados)
    if todos_simulados:
        resultado = "simulado"
    else:
        resultado = "enviado" if todos else "enviado_con_errores"
    return {"pedidos": resultados, "resultado": resultado}


def rechazar_pedidos(estado: Estado) -> dict:
    motivo = estado["decision"].get("motivo", "")

    async def tarea():
        async with servidor("mcp_pedidos.py") as pedidos_mcp:
            for pedido in estado["pedidos"]:
                await llamar(pedidos_mcp, "rechazar_pedido",
                             {"pedido_id": pedido["pedido_id"], "motivo": motivo})

    asyncio.run(tarea())
    return {"resultado": "rechazado"}


def dejar_pendiente(estado: Estado) -> dict:
    """El dueño no decidió: los pedidos quedan pendientes y no se envía nada."""
    async def tarea():
        async with servidor("mcp_pedidos.py") as pedidos_mcp:
            for pedido in estado["pedidos"]:
                await llamar(pedidos_mcp, "dejar_pendiente", {"pedido_id": pedido["pedido_id"]})

    asyncio.run(tarea())
    return {"resultado": "pendiente"}


def registrar(estado: Estado) -> dict:
    """Deja constancia en la bitácora y fija el resultado final."""
    resultado = estado.get("resultado") or (
        "solo_sin_proveedor" if estado.get("sin_proveedor") else "sin_novedades")
    detalle = (f"pedidos={len(estado.get('pedidos', []))}, "
               f"sin_proveedor={estado.get('sin_proveedor', [])}")

    async def tarea():
        async with servidor("mcp_pedidos.py") as pedidos_mcp:
            await llamar(pedidos_mcp, "registrar_bitacora",
                         {"nodo": "grafo", "evento": resultado, "detalle": detalle})

    asyncio.run(tarea())
    return {"resultado": resultado, "sin_proveedor": estado.get("sin_proveedor", [])}


# ---------------- Decisiones (las flechas con condición) ----------------

def despues_de_revisar(estado: Estado) -> str:
    return "armar_pedidos" if estado["criticos"] else "registrar"


def despues_de_actualizar_cotizacion(estado: Estado) -> str:
    return "esperar_dueno" if estado["criticos"] or estado["sin_proveedor"] else "registrar"


def elegir_camino(estado: Estado) -> str:
    accion = estado["decision"]["accion"]
    if accion == "aprobar":
        return "enviar_pedidos"
    if accion == "rechazar":
        return "rechazar_pedidos"
    if accion == "ajustar":
        return "ajustar_pedido"
    if accion == "agregar_cotizacion":
        return "agregar_cotizacion"
    if accion == "pendiente":
        return "posponer"
    if accion == "ambiguo" and estado["rondas_aclaracion"] < MAX_ACLARACIONES:
        return "pedir_aclaracion"
    return "dejar_pendiente"      # "pendiente", o ya se agotaron las aclaraciones


# ---------------- Armado del grafo ----------------

def construir_grafo(checkpointer):
    g = StateGraph(Estado)
    g.add_node("revisar", revisar)
    g.add_node("armar_pedidos", armar_pedidos)
    g.add_node("esperar_dueno", esperar_dueno)
    g.add_node("interpretar", interpretar)
    g.add_node("ajustar_pedido", ajustar_pedido)
    g.add_node("agregar_cotizacion", agregar_cotizacion)
    g.add_node("posponer", posponer)
    g.add_node("pedir_aclaracion", pedir_aclaracion)
    g.add_node("enviar_pedidos", enviar_pedidos)
    g.add_node("rechazar_pedidos", rechazar_pedidos)
    g.add_node("dejar_pendiente", dejar_pendiente)
    g.add_node("registrar", registrar)

    g.add_edge(START, "revisar")
    g.add_conditional_edges("revisar", despues_de_revisar,
                            {"armar_pedidos": "armar_pedidos", "registrar": "registrar"})
    g.add_edge("armar_pedidos", "esperar_dueno")
    g.add_edge("esperar_dueno", "interpretar")
    g.add_conditional_edges("interpretar", elegir_camino, {
        "enviar_pedidos": "enviar_pedidos",
        "rechazar_pedidos": "rechazar_pedidos",
        "ajustar_pedido": "ajustar_pedido",
        "agregar_cotizacion": "agregar_cotizacion",
        "posponer": "posponer",
        "pedir_aclaracion": "pedir_aclaracion",
        "dejar_pendiente": "dejar_pendiente",
    })
    g.add_edge("ajustar_pedido", "esperar_dueno")
    g.add_conditional_edges("agregar_cotizacion", despues_de_actualizar_cotizacion, {
        "esperar_dueno": "esperar_dueno",
        "registrar": "registrar",
    })
    g.add_edge("posponer", "esperar_dueno")
    g.add_edge("pedir_aclaracion", "esperar_dueno")
    g.add_edge("enviar_pedidos", "registrar")
    g.add_edge("rechazar_pedidos", "registrar")
    g.add_edge("dejar_pendiente", "registrar")
    g.add_edge("registrar", END)
    return g.compile(checkpointer=checkpointer)