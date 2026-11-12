import pytest

from calculo.gemini import (
    ErrorDeInterpretacion, _solicitar_groq, _solicitar_seleccion,
    seleccionar_productos,
)


def producto(sku, titulo, proveedor_recomendado="A"):
    opciones = [
        {
            "proveedor": "A",
            "cantidad_a_pedir": 24,
            "precio_unitario_cop": 100,
            "empaque": 6,
            "pedido_minimo_unidades": 12,
        },
        {
            "proveedor": "B",
            "cantidad_a_pedir": 48,
            "precio_unitario_cop": 80,
            "empaque": 6,
            "pedido_minimo_unidades": 24,
        },
    ]
    recomendada = next(o for o in opciones if o["proveedor"] == proveedor_recomendado)
    return {
        "sku": sku,
        "titulo_producto": titulo,
        "opciones": opciones,
        "recomendada": recomendada,
    }


def test_selecciona_solo_productos_mencionados_y_cambia_proveedor(monkeypatch):
    candidatos = [producto(10, "Funda azul"), producto(20, "Cable USB")]
    monkeypatch.setattr(
        "calculo.gemini._solicitar_seleccion",
        lambda instruccion, criticos: [{"sku": 10, "proveedor": "B", "cantidad": None}],
    )

    seleccion, ajustes = seleccionar_productos("Pide la funda con B", candidatos)

    assert [p["sku"] for p in seleccion] == [10]
    assert seleccion[0]["recomendada"]["proveedor"] == "A"
    assert seleccion[0]["seleccionada"]["proveedor"] == "B"
    assert seleccion[0]["seleccionada"]["cantidad_a_pedir"] == 48
    assert ajustes == []


def test_ajusta_cantidad_al_empaque_y_al_minimo(monkeypatch):
    candidatos = [producto(10, "Funda azul")]
    monkeypatch.setattr(
        "calculo.gemini._solicitar_seleccion",
        lambda instruccion, criticos: [{"sku": 10, "proveedor": "A", "cantidad": 5}],
    )

    seleccion, ajustes = seleccionar_productos("Pide cinco", candidatos)

    assert seleccion[0]["seleccionada"]["cantidad_a_pedir"] == 12
    assert seleccion[0]["seleccionada"]["total_cop"] == 1200
    assert "requieren 12 unidades" in ajustes[0]


def test_redondea_el_pedido_minimo_al_empaque_completo(monkeypatch):
    candidatos = [producto(10, "Funda azul")]
    candidatos[0]["opciones"][0]["pedido_minimo_unidades"] = 10
    monkeypatch.setattr(
        "calculo.gemini._solicitar_seleccion",
        lambda instruccion, criticos: [{"sku": 10, "proveedor": "A", "cantidad": 1}],
    )

    seleccion, ajustes = seleccionar_productos("Pide una", candidatos)

    assert seleccion[0]["seleccionada"]["cantidad_a_pedir"] == 12
    assert "requieren 12 unidades" in ajustes[0]


def test_solicita_a_gemini_json_estructurado(monkeypatch):
    llamada = {}

    class Respuesta:
        ok = True

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{
                "content": {"parts": [{"text": '{"items": [{"sku": 10, "proveedor": null, "cantidad": null}]}'}]}
            }]}

    def post(url, **kwargs):
        llamada["url"] = url
        llamada.update(kwargs)
        return Respuesta()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("calculo.gemini.requests.post", post)

    seleccion = _solicitar_seleccion("Pide la funda azul", [producto(10, "Funda azul")])

    assert seleccion == [{"sku": 10, "proveedor": None, "cantidad": None}]
    assert llamada["url"].endswith("/gemini-3.8-flash:generateContent")
    assert llamada["params"] == {"key": "test-key"}
    assert llamada["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_rechaza_clave_no_ascii_sin_hacer_peticion(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-con-caracter-no-ascii-ñ")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        "calculo.gemini.requests.post",
        lambda *args, **kwargs: pytest.fail("No debe llamar a Gemini con una clave malformada"),
    )

    with pytest.raises(ErrorDeInterpretacion, match="caracteres no válidos"):
        _solicitar_seleccion("selecciona la funda", [producto(10, "Funda azul")])


def test_muestra_el_error_http_de_gemini_sin_ocultar_la_causa(monkeypatch):
    class Respuesta:
        ok = False
        status_code = 404

        def json(self):
            return {"error": {"message": "Model not found for API version"}}

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("calculo.gemini.requests.post", lambda *args, **kwargs: Respuesta())

    with pytest.raises(
        ErrorDeInterpretacion,
        match="HTTP 404\\. Detalle: Model not found for API version",
    ):
        _solicitar_seleccion("selecciona la funda", [producto(10, "Funda azul")])


def test_reintenta_fallos_503_temporales(monkeypatch):
    class Respuesta:
        def __init__(self, ok, status_code):
            self.ok = ok
            self.status_code = status_code

        def json(self):
            if self.ok:
                return {"candidates": [{
                    "content": {"parts": [{"text": '{"items": [{"sku": 10, "proveedor": null, "cantidad": null}]}'}]}
                }]}
            return {"error": {"message": "Temporary high demand"}}

    respuestas = iter([
        Respuesta(False, 503),
        Respuesta(False, 503),
        Respuesta(True, 200),
    ])
    llamadas = []
    pausas = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "calculo.gemini.requests.post",
        lambda *args, **kwargs: (llamadas.append(args[0]), next(respuestas))[1],
    )
    monkeypatch.setattr("calculo.gemini.time.sleep", pausas.append)

    resultado = _solicitar_seleccion("selecciona la funda", [producto(10, "Funda azul")])

    assert resultado == [{"sku": 10, "proveedor": None, "cantidad": None}]
    assert len(llamadas) == 3
    assert pausas == [1, 2]


def test_devuelve_error_despues_de_agotar_reintentos_503(monkeypatch):
    class Respuesta:
        ok = False
        status_code = 503

        def json(self):
            return {"error": {"message": "Temporary high demand"}}

    llamadas = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        "calculo.gemini.requests.post",
        lambda *args, **kwargs: (llamadas.append(True), Respuesta())[1],
    )
    monkeypatch.setattr("calculo.gemini.time.sleep", lambda _: None)

    with pytest.raises(
        ErrorDeInterpretacion,
        match="HTTP 503\\. Detalle: Temporary high demand",
    ):
        _solicitar_seleccion("selecciona la funda", [producto(10, "Funda azul")])

    assert len(llamadas) == 3


def test_usa_groq_si_gemini_falla(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    intentos = []

    def falla_gemini(*args):
        intentos.append("gemini")
        raise ErrorDeInterpretacion("Gemini respondió HTTP 503.")

    def responde_groq(api_key, prompt):
        intentos.append("groq")
        assert api_key == "groq-test-key"
        assert "Funda azul" in prompt
        return [{"sku": 10, "proveedor": "A", "cantidad": None}]

    monkeypatch.setattr("calculo.gemini._solicitar_gemini", falla_gemini)
    monkeypatch.setattr("calculo.gemini._solicitar_groq", responde_groq)

    resultado = _solicitar_seleccion("Pide la funda azul", [producto(10, "Funda azul")])

    assert resultado == [{"sku": 10, "proveedor": "A", "cantidad": None}]
    assert intentos == ["gemini", "groq"]


def test_usa_groq_directamente_si_no_hay_clave_de_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setattr(
        "calculo.gemini._solicitar_groq",
        lambda api_key, prompt: [{"sku": 10, "proveedor": "B", "cantidad": 12}],
    )
    monkeypatch.setattr(
        "calculo.gemini._solicitar_gemini",
        lambda *args: pytest.fail("No debe llamar a Gemini si no hay una clave"),
    )

    resultado = _solicitar_seleccion("Pide funda", [producto(10, "Funda azul")])

    assert resultado == [{"sku": 10, "proveedor": "B", "cantidad": 12}]


def test_groq_envia_autorizacion_y_json_mode(monkeypatch):
    llamada = {}

    class Respuesta:
        ok = True
        status_code = 200

        def json(self):
            return {"choices": [{
                "message": {"content": '{"items": [{"sku": 10, "proveedor": "B", "cantidad": 12}]}'}
            }]}

    def post(url, **kwargs):
        llamada["url"] = url
        llamada.update(kwargs)
        return Respuesta()

    monkeypatch.setattr("calculo.gemini.requests.post", post)

    resultado = _solicitar_groq(
        "groq-test-key",
        "Instrucción de prueba",
    )

    assert resultado == [{"sku": 10, "proveedor": "B", "cantidad": 12}]
    assert llamada["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert llamada["headers"]["Authorization"] == "Bearer groq-test-key"
    assert llamada["json"]["model"] == "openai/gpt-oss-120b"
    assert llamada["json"]["response_format"] == {"type": "json_object"}


def test_reporta_error_de_ambos_proveedores(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    def falla_gemini(*args):
        raise ErrorDeInterpretacion("Gemini HTTP 503")

    def falla_groq(*args):
        raise ErrorDeInterpretacion("Groq HTTP 429")

    monkeypatch.setattr("calculo.gemini._solicitar_gemini", falla_gemini)
    monkeypatch.setattr("calculo.gemini._solicitar_groq", falla_groq)

    with pytest.raises(ErrorDeInterpretacion, match="Gemini HTTP 503.*Groq HTTP 429"):
        _solicitar_seleccion("Pide funda", [producto(10, "Funda azul")])


def test_error_claro_si_no_hay_ninguna_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ErrorDeInterpretacion, match="GEMINI_API_KEY o GROQ_API_KEY"):
        _solicitar_seleccion("Pide funda", [producto(10, "Funda azul")])


@pytest.mark.parametrize(
    "respuesta, mensaje",
    [
        ([{"sku": 999, "proveedor": "A", "cantidad": None}], "no está entre"),
        ([{"sku": 10, "proveedor": "Desconocido", "cantidad": None}], "no surte"),
        ([{"sku": 10, "proveedor": "A", "cantidad": 0}], "mayor que cero"),
        (
            [
                {"sku": 10, "proveedor": "A", "cantidad": None},
                {"sku": 10, "proveedor": "B", "cantidad": None},
            ],
            "más de una vez",
        ),
    ],
)
def test_rechaza_respuestas_fuera_de_las_opciones(monkeypatch, respuesta, mensaje):
    monkeypatch.setattr(
        "calculo.gemini._solicitar_seleccion",
        lambda instruccion, criticos: respuesta,
    )

    with pytest.raises(ErrorDeInterpretacion, match=mensaje):
        seleccionar_productos("selecciona", [producto(10, "Funda azul")])
