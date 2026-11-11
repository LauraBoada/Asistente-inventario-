# Prueba los textos, botones y la traducción de la respuesta del dueño del bot de
# Telegram. No importa la librería de Telegram ni se conecta a nada.
from bot.mensajes import botones_cotizacion, decision_desde_callback, formatear_cotizacion, formatear_resumen

COTIZACION = {
    "sku": 12097,
    "titulo_producto": "Funda Contra Agua Sumergible",
    "opciones": [
        {"proveedor": "Distribuidora Andina", "cantidad_a_pedir": 108, "total_cop": 466560, "llega_tarde": False},
        {"proveedor": "Mayorista Central", "cantidad_a_pedir": 144, "total_cop": 400000, "llega_tarde": True},
    ],
    "recomendada": {"proveedor": "Distribuidora Andina", "cantidad_a_pedir": 108, "total_cop": 466560},
}


def test_formatear_cotizacion_incluye_sku_opciones_y_marca_la_recomendada():
    texto = formatear_cotizacion(COTIZACION)

    assert "12097" in texto
    assert "Funda Contra Agua Sumergible" in texto
    assert "✅ Distribuidora Andina" in texto
    assert "• Mayorista Central" in texto
    assert "(llega tarde)" in texto


def test_botones_cotizacion_una_fila_por_proveedor_y_una_para_rechazar():
    filas = botones_cotizacion(COTIZACION)

    assert len(filas) == 3  # 2 proveedores + rechazar
    assert filas[0][0][1] == "aprobar:12097:Distribuidora Andina"
    assert filas[1][0][1] == "aprobar:12097:Mayorista Central"
    assert filas[2][0][1] == "rechazar:12097"
    assert filas[0][0][0].startswith("✅ ")  # la recomendada queda marcada en el texto del botón


def test_decision_desde_callback_aprobar():
    decision = decision_desde_callback("aprobar:12097:Distribuidora Andina", "Laura")
    assert decision == {"aprueba": True, "proveedor": "Distribuidora Andina", "aprobado_por": "Laura"}


def test_decision_desde_callback_rechazar():
    decision = decision_desde_callback("rechazar:12097", "Laura")
    assert decision == {"aprueba": False, "motivo": "Rechazado por Laura vía Telegram"}


def test_formatear_resumen_con_enviados_rechazados_y_sin_proveedor():
    estado = {
        "criticos": [{"sku": 1}, {"sku": 2}],
        "sin_proveedor": [3],
        "decisiones": [
            {"sku": 1, "aprobado": True, "pedido_id": "abc123", "motivo": None},
            {"sku": 2, "aprobado": False, "pedido_id": None, "motivo": "El dueño no aprobó el pedido"},
        ],
    }

    texto = formatear_resumen(estado)

    assert "Pedidos enviados (simulado): 1" in texto
    assert "abc123" in texto
    assert "Sin enviar: 1" in texto
    assert "El dueño no aprobó el pedido" in texto
    assert "[3]" in texto


def test_formatear_resumen_sin_criticos():
    estado = {"criticos": [], "sin_proveedor": [], "decisiones": []}
    texto = formatear_resumen(estado)
    assert "Ningún producto está en punto de reorden" in texto


def test_formatear_resumen_distingue_envio_por_gmail():
    estado = {
        "criticos": [{"sku": 1}],
        "sin_proveedor": [],
        "decisiones": [
            {"sku": 1, "aprobado": True, "estado_envio": "enviado", "pedido_id": "pedido-gmail"},
        ],
    }

    texto = formatear_resumen(estado)

    assert "Pedidos enviados por Gmail: 1" in texto
    assert "pedido-gmail" in texto
