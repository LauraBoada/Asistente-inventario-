from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from grafo.inventario_grafo import (
    _agrupar_por_proveedor, _resumen_productos, despues_de_actualizar_cotizacion,
    elegir_camino, posponer,
)


def test_pendiente_conserva_la_revision_y_permite_retomar():
    def esperar(_estado):
        return {"respuesta": interrupt("¿Apruebas?")}

    def registrar(estado):
        return {"resultado": estado["respuesta"]}

    grafo = StateGraph(dict)
    grafo.add_node("esperar", esperar)
    grafo.add_node("registrar", registrar)
    grafo.add_edge(START, "esperar")
    grafo.add_edge("esperar", "registrar")
    grafo.add_edge("registrar", END)
    checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "revision-prueba"}}

    assert grafo.compile(checkpointer=checkpointer).invoke({}, config)["__interrupt__"]
    reiniciado = grafo.compile(checkpointer=checkpointer)
    assert reiniciado.get_state(config).next == ("esperar",)
    resultado = reiniciado.invoke(Command(resume="aprobar"), config)

    assert resultado["resultado"] == "aprobar"


def test_dejar_pendiente_vuelve_a_mostrar_botones_sin_cerrar_revision():
    assert elegir_camino({"decision": {"accion": "pendiente"}, "rondas_aclaracion": 0}) == "posponer"
    assert posponer({})["mensaje_revision"].endswith("/pendientes.")


def test_pedidos_se_agrupan_por_la_opcion_que_selecciono_el_dueno():
    productos = [{
        "sku": 10,
        "recomendada": {"proveedor": "A", "cantidad_a_pedir": 24, "precio_unitario_cop": 100},
        "seleccionada": {"proveedor": "B", "cantidad_a_pedir": 12, "precio_unitario_cop": 80},
    }]

    grupos = _agrupar_por_proveedor(productos, "seleccionada")

    assert grupos == {"B": [{"sku": 10, "cantidad": 12, "precio_unitario_cop": 80}]}


def test_resumen_mantiene_la_recomendacion_y_muestra_la_eleccion_del_dueno():
    productos = [{
        "sku": 10,
        "titulo_producto": "Funda azul",
        "opciones": [
            {"proveedor": "A", "cantidad_a_pedir": 24, "total_cop": 2400,
             "plazo_dias": 2, "llega_tarde": False, "empaque": 6,
             "pedido_minimo_unidades": 12},
            {"proveedor": "B", "cantidad_a_pedir": 48, "total_cop": 3840,
             "plazo_dias": 4, "llega_tarde": False, "empaque": 6,
             "pedido_minimo_unidades": 24},
        ],
        "recomendada": {
            "proveedor": "A", "cantidad_a_pedir": 24, "total_cop": 2400,
        },
        "seleccionada": {
            "proveedor": "B", "cantidad_a_pedir": 30, "total_cop": 2400,
        },
    }]

    resumen = _resumen_productos(productos)[0]

    assert resumen["recomendada"] == "A"
    assert resumen["seleccionada"] == "B"
    assert resumen["opciones"][0]["recomendada"] is True
    assert resumen["opciones"][0]["seleccionada"] is False
    assert resumen["opciones"][1]["seleccionada"] is True
    assert resumen["opciones"][1]["cantidad"] == 30


def test_resumen_inicial_marca_recomendacion_sin_indicar_seleccion_del_dueno():
    producto = {
        "sku": 10,
        "titulo_producto": "Funda azul",
        "opciones": [{
            "proveedor": "A",
            "cantidad_a_pedir": 24,
            "total_cop": 2400,
            "plazo_dias": 2,
            "llega_tarde": False,
            "empaque": 6,
            "pedido_minimo_unidades": 12,
        }],
        "recomendada": {
            "proveedor": "A", "cantidad_a_pedir": 24, "total_cop": 2400,
        },
    }

    resumen = _resumen_productos([producto])[0]

    assert resumen["opciones"][0]["recomendada"] is True
    assert resumen["opciones"][0]["seleccionada"] is False
    assert resumen["seleccionada"] is None


def test_actualizar_cotizacion_retorna_a_revision_si_hay_productos():
    assert despues_de_actualizar_cotizacion({"criticos": [], "sin_proveedor": [10]}) == "esperar_dueno"
    assert despues_de_actualizar_cotizacion({"criticos": [1], "sin_proveedor": []}) == "esperar_dueno"
    assert despues_de_actualizar_cotizacion({"criticos": [], "sin_proveedor": []}) == "registrar"


def test_ajustar_pedido_sin_api_key_deja_el_pedido_original_pendiente(monkeypatch):
    from grafo.inventario_grafo import ajustar_pedido

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    estado = {
        "decision": {"instruccion": "Pide la funda azul"},
        "criticos": [{
            "sku": 1,
            "titulo_producto": "Funda azul",
            "opciones": [],
            "recomendada": {},
        }],
        "pedidos": [{"pedido_id": "pedido-original", "proveedor": "A"}],
    }

    resultado = ajustar_pedido(estado)

    assert resultado["decision"] == {}
    assert "GEMINI_API_KEY" in resultado["mensaje_revision"]
    assert resultado["rondas_aclaracion"] == 0
