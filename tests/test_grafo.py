# Pruebas del grafo del coordinador: nodos sueltos (sin pasar por LangGraph) y el flujo
# completo con pausa para aprobación y ciclos con límite. No toca Mongo: mcp-inventario y
# mcp-pedidos quedan reemplazados por funciones falsas.
from langgraph.types import Command

import grafo.nodos as nodos
from grafo.coordinador import construir_grafo
from grafo.estado import estado_inicial
from grafo.nodos import hay_pendientes, procesar_decision

CRITICO = {
    "sku": 1,
    "titulo_producto": "Funda crítica",
    "opciones": [
        {"proveedor": "Distribuidora Andina", "cantidad_a_pedir": 36, "total_cop": 155520, "llega_tarde": False},
        {"proveedor": "Mayorista Central", "cantidad_a_pedir": 48, "total_cop": 120000, "llega_tarde": True},
    ],
    "recomendada": {"proveedor": "Distribuidora Andina", "cantidad_a_pedir": 36, "total_cop": 155520},
}


# ---- hay_pendientes (decisión de flujo, sin LLM) --------------------------------------

def test_hay_pendientes_con_criticos_sin_revisar():
    estado = {**estado_inicial(), "criticos": [CRITICO], "indice": 0, "ciclos": 0, "limite_ciclos": 5}
    assert hay_pendientes(estado) == "revisar_siguiente"


def test_hay_pendientes_sin_mas_criticos():
    estado = {**estado_inicial(), "criticos": [CRITICO], "indice": 1, "ciclos": 1, "limite_ciclos": 5}
    assert hay_pendientes(estado) == "fin"


def test_hay_pendientes_respeta_limite_de_ciclos():
    estado = {**estado_inicial(), "criticos": [CRITICO, CRITICO], "indice": 0, "ciclos": 1, "limite_ciclos": 1}
    assert hay_pendientes(estado) == "fin"


# ---- procesar_decision (qué pasa con un crítico tras la aprobación) -------------------

def test_procesar_decision_rechazada_no_llama_a_pedidos(monkeypatch):
    llamado = []
    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido", lambda **kw: llamado.append(kw))
    monkeypatch.setattr(nodos, "enviar_pedido", lambda aprobacion_id: llamado.append(aprobacion_id))

    resultado = procesar_decision(CRITICO, {"aprueba": False, "motivo": "Esta semana no"})

    assert resultado == {"sku": 1, "aprobado": False, "pedido_id": None, "motivo": "Esta semana no"}
    assert llamado == []


def test_procesar_decision_aprobada_usa_la_recomendada_por_defecto(monkeypatch):
    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido",
                         lambda **kw: {"aprobacion_id": "aprob-1"})
    monkeypatch.setattr(nodos, "enviar_pedido",
                         lambda aprobacion_id: {"estado": "simulado_enviado", "pedido_id": "pedido-1"})

    resultado = procesar_decision(CRITICO, {"aprueba": True, "aprobado_por": "dueño"})

    assert resultado == {"sku": 1, "aprobado": True, "pedido_id": "pedido-1", "motivo": None}


def test_procesar_decision_aprobada_con_proveedor_elegido(monkeypatch):
    capturado = {}

    def falso_registrar(**kw):
        capturado.update(kw)
        return {"aprobacion_id": "aprob-2"}

    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido", falso_registrar)
    monkeypatch.setattr(nodos, "enviar_pedido",
                         lambda aprobacion_id: {"estado": "simulado_enviado", "pedido_id": "pedido-2"})

    procesar_decision(CRITICO, {"aprueba": True, "proveedor": "Mayorista Central"})

    assert capturado["proveedor"] == "Mayorista Central"
    assert capturado["cantidad"] == 48


def test_procesar_decision_proveedor_inexistente_no_llama_a_pedidos(monkeypatch):
    llamado = []
    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido", lambda **kw: llamado.append(kw))

    resultado = procesar_decision(CRITICO, {"aprueba": True, "proveedor": "Proveedor que no existe"})

    assert resultado["aprobado"] is False
    assert "no está entre las opciones" in resultado["motivo"]
    assert llamado == []


# ---- grafo completo: pausa para aprobación y ciclos con límite ------------------------

PRODUCTOS = [
    {"sku": 1, "titulo_producto": "Funda crítica", "demanda_diaria": 2, "stock_actual": 0,
     "pedidos_en_camino": 0, "empaque": 12},
    {"sku": 2, "titulo_producto": "Funda sin proveedor", "demanda_diaria": 2, "stock_actual": 0,
     "pedidos_en_camino": 0, "empaque": 12},
    {"sku": 3, "titulo_producto": "Funda con stock de sobra", "demanda_diaria": 1, "stock_actual": 1000,
     "pedidos_en_camino": 0, "empaque": 6},
]
CATALOGO = {
    1: [{"proveedor": "Distribuidora Andina", "precio_unitario_cop": 100, "plazo_dias": 2, "pedido_minimo_unidades": 12}],
}


def _preparar_herramientas(monkeypatch):
    monkeypatch.setattr(nodos, "listar_productos", lambda: PRODUCTOS)
    monkeypatch.setattr(nodos, "listar_catalogo_proveedores", lambda: CATALOGO)
    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido",
                         lambda **kw: {"aprobacion_id": f"aprob-{kw['sku']}"})
    monkeypatch.setattr(nodos, "enviar_pedido",
                         lambda aprobacion_id: {"estado": "simulado_enviado", "pedido_id": f"pedido-{aprobacion_id}"})


def test_grafo_completo_pausa_y_envia_el_pedido_aprobado(monkeypatch):
    _preparar_herramientas(monkeypatch)
    app = construir_grafo()
    config = {"configurable": {"thread_id": "prueba-1"}}

    resultado = app.invoke(estado_inicial(), config=config)

    assert "__interrupt__" in resultado
    cotizacion = resultado["__interrupt__"][0].value
    assert cotizacion["sku"] == 1  # el único crítico con proveedor

    resultado = app.invoke(Command(resume={"aprueba": True, "aprobado_por": "dueño"}), config=config)

    assert resultado["terminado"] is True
    assert resultado["sin_proveedor"] == [2]
    assert resultado["decisiones"] == [
        {"sku": 1, "aprobado": True, "pedido_id": "pedido-aprob-1", "motivo": None},
    ]


def test_grafo_completo_rechazo_no_crea_pedido(monkeypatch):
    _preparar_herramientas(monkeypatch)
    app = construir_grafo()
    config = {"configurable": {"thread_id": "prueba-2"}}

    app.invoke(estado_inicial(), config=config)
    resultado = app.invoke(Command(resume={"aprueba": False, "motivo": "No por ahora"}), config=config)

    assert resultado["terminado"] is True
    assert resultado["decisiones"] == [{"sku": 1, "aprobado": False, "pedido_id": None, "motivo": "No por ahora"}]


def test_grafo_sin_criticos_termina_directo(monkeypatch):
    monkeypatch.setattr(nodos, "listar_productos", lambda: [PRODUCTOS[2]])  # solo el que tiene stock de sobra
    monkeypatch.setattr(nodos, "listar_catalogo_proveedores", lambda: {})
    app = construir_grafo()
    config = {"configurable": {"thread_id": "prueba-3"}}

    resultado = app.invoke(estado_inicial(), config=config)

    assert "__interrupt__" not in resultado
    assert resultado["terminado"] is True
    assert resultado["criticos"] == []


def test_grafo_corta_por_limite_de_ciclos(monkeypatch):
    dos_criticos = [PRODUCTOS[0], {**PRODUCTOS[0], "sku": 9, "titulo_producto": "Otra funda crítica"}]
    monkeypatch.setattr(nodos, "listar_productos", lambda: dos_criticos)
    monkeypatch.setattr(nodos, "listar_catalogo_proveedores", lambda: {1: CATALOGO[1], 9: CATALOGO[1]})
    monkeypatch.setattr(nodos, "registrar_aprobacion_pedido",
                         lambda **kw: {"aprobacion_id": f"aprob-{kw['sku']}"})
    monkeypatch.setattr(nodos, "enviar_pedido",
                         lambda aprobacion_id: {"estado": "simulado_enviado", "pedido_id": f"pedido-{aprobacion_id}"})

    app = construir_grafo()
    config = {"configurable": {"thread_id": "prueba-4"}}

    resultado = app.invoke({**estado_inicial(limite_ciclos=1)}, config=config)
    assert "__interrupt__" in resultado
    resultado = app.invoke(Command(resume={"aprueba": True, "aprobado_por": "dueño"}), config=config)

    # El límite de ciclos (1) corta el flujo después de revisar un solo crítico, aunque
    # había dos: evita un ciclo sin fin si algo falla.
    assert resultado["terminado"] is True
    assert len(resultado["decisiones"]) == 1
