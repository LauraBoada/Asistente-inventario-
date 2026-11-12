from calculo.correo import preparar_correo, resolver_destinatario
from bot.mensajes import formatear_cotizacion, formatear_resultado


def test_preparar_correo_incluye_destinatario_items_y_total():
    correo = preparar_correo({
        "proveedor": "Distribuidora Andina",
        "items": [{"sku": 12097, "cantidad": 12, "precio_unitario_cop": 4320}],
        "total_cop": 51840,
    }, "pedidos@proveedor.example")

    assert correo["destinatario"] == "pedidos@proveedor.example"
    assert "Distribuidora Andina" in correo["asunto"]
    assert "Estimado equipo de Distribuidora Andina:" in correo["cuerpo"]
    assert "Reciban un cordial saludo." in correo["cuerpo"]
    assert "solicitud de reposición correspondiente a " in correo["cuerpo"]
    assert "SKU 12097: 12 unidades" in correo["cuerpo"]
    assert "$51,840 COP" in correo["cuerpo"]
    assert "Quedamos atentos. Muchas gracias por su atención." in correo["cuerpo"]


def test_correo_informa_si_el_proveedor_no_tiene_contacto():
    correo = preparar_correo({
        "proveedor": "Proveedor sin correo",
        "items": [{"sku": 1, "cantidad": 1, "precio_unitario_cop": 0}],
        "total_cop": 0,
    }, None)

    assert correo["destinatario"] == "No registrado en el catálogo"


def test_destinatario_de_prueba_redirige_solo_en_modo_gmail():
    assert resolver_destinatario(
        "proveedor@example.com",
        "gmail",
        "  pedidosagenteia@gmail.com ",
    ) == "pedidosagenteia@gmail.com"
    assert resolver_destinatario(
        "proveedor@example.com",
        "simulado",
        "pedidosagenteia@gmail.com",
    ) == "proveedor@example.com"


def test_sin_override_conserva_el_contacto_del_proveedor():
    assert resolver_destinatario("proveedor@example.com", "gmail") == "proveedor@example.com"


def test_resultado_simulado_deja_claro_que_no_envio_el_correo():
    texto = formatear_resultado({
        "resultado": "simulado",
        "pedidos": [{
            "proveedor": "Distribuidora Andina",
            "estado": "simulado",
            "correo": {
                "canal": "simulado",
                "destinatario": "pedidos@example.com",
                "asunto": "Pedido de reposición",
                "cuerpo": "SKU 10: 12 unidades",
            },
        }],
    })

    assert "no se envió ningún correo" in texto
    assert "Vista previa (no enviada)" in texto
    assert "SKU 10" in texto


def test_resultado_explica_productos_criticos_sin_proveedor():
    texto = formatear_resultado({
        "resultado": "solo_sin_proveedor",
        "sin_proveedor": [12097, 83810],
    })

    assert "Sin proveedor: 12097, 83810" in texto
    assert "No se genera pedido" in texto


def test_resultado_muestra_el_motivo_del_fallo_de_correo():
    texto = formatear_resultado({
        "resultado": "enviado_con_errores",
        "pedidos": [{
            "proveedor": "Distribuidora Andina",
            "estado": "error",
            "detalle": "Autenticación SMTP rechazada",
        }],
    })

    assert "Distribuidora Andina: error" in texto
    assert "Motivo: Autenticación SMTP rechazada" in texto


def test_cotizacion_ajustada_formatea_lista_de_pedidos():
    texto = formatear_cotizacion({
        "mensaje": "Confirmación de tu selección: 1 producto.",
        "criticos": [{
            "sku": 10,
            "titulo": "Funda azul",
            "recomendada": "Proveedor A",
            "seleccionada": "Proveedor B",
            "opciones": [{
                "proveedor": "Proveedor A",
                "cantidad": 24,
                "total_cop": 2400,
                "plazo_dias": 3,
                "llega_tarde": False,
                "recomendada": True,
                "seleccionada": False,
            }, {
                "proveedor": "Proveedor B",
                "cantidad": 12,
                "total_cop": 1800,
                "plazo_dias": 4,
                "llega_tarde": False,
                "recomendada": False,
                "seleccionada": True,
            }],
        }],
        "pedidos": [{
            "pedido_id": "pedido-1",
            "proveedor": "Proveedor B",
            "productos": 1,
            "total_cop": 1800,
        }],
        "sin_proveedor": [],
    })

    assert "Funda azul (10)" in texto
    assert "⭐ Proveedor A: 24 unid. · $2,400" in texto
    assert "✅ Proveedor B: 12 unid. · $1,800" in texto
    assert "Proveedor B: 1 producto · $1,800" in texto


def test_cotizacion_sin_proveedor_indica_que_se_captura_por_chat():
    texto = formatear_cotizacion({
        "criticos": [],
        "pedidos": [],
        "sin_proveedor": [486884],
    })

    assert "Cotización pendiente para estos SKU: 486884" in texto
    assert "Pulsa «Agregar cotización»" in texto
