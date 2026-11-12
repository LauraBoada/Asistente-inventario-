"""Interpreta instrucciones de compra usando Gemini y valida la selección localmente."""

import json
import math
import os
import time

import requests

MAX_INTENTOS_GEMINI = 3
ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}
URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
MODELO_GROQ_PREDETERMINADO = "openai/gpt-oss-120b"


class ErrorDeInterpretacion(Exception):
    """La instrucción no pudo interpretarse o no corresponde al inventario disponible."""


def _preparar_prompt(instruccion, criticos):
    candidatos = [{
        "sku": c["sku"],
        "producto": c.get("titulo", c.get("titulo_producto", "")),
        "proveedores": [{
            "nombre": o["proveedor"],
            "unidades_recomendadas": o["cantidad_a_pedir"],
            "precio_unitario_cop": o["precio_unitario_cop"],
            "empaque": o["empaque"],
            "minimo_proveedor": o["pedido_minimo_unidades"],
        } for o in c["opciones"]],
    } for c in criticos]
    esquema = {
        "type": "OBJECT",
        "properties": {
            "items": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "sku": {"type": "INTEGER"},
                        "proveedor": {"type": "STRING", "nullable": True},
                        "cantidad": {"type": "INTEGER", "nullable": True},
                    },
                    "required": ["sku", "proveedor", "cantidad"],
                },
            },
        },
        "required": ["items"],
    }
    prompt = (
        "Interpreta la instrucción del dueño y selecciona únicamente productos del "
        "inventario candidato. Devuelve cada producto solicitado una sola vez. "
        "Si no especifica proveedor, usa null. Si no especifica cantidad, usa null. "
        "No inventes SKU ni proveedores. Si la instrucción es ambigua, devuelve items vacío.\n"
        f"Candidatos: {json.dumps(candidatos, ensure_ascii=False)}\n"
        f"Instrucción: {instruccion}"
    )
    return prompt, esquema


def _pedir_json(proveedor, url, payload, *, headers=None, params=None):
    for intento in range(MAX_INTENTOS_GEMINI):
        try:
            respuesta = requests.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except requests.RequestException as error:
            if intento + 1 == MAX_INTENTOS_GEMINI:
                raise ErrorDeInterpretacion(
                    f"No se pudo conectar con {proveedor} después de varios intentos. "
                    "Verifica tu conexión a Internet y vuelve a intentar."
                ) from error
            time.sleep(2**intento)
            continue

        if respuesta.ok or respuesta.status_code not in ESTADOS_REINTENTABLES:
            break
        if intento + 1 < MAX_INTENTOS_GEMINI:
            time.sleep(2**intento)

    if not respuesta.ok:
        try:
            detalle = respuesta.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detalle = ""
        detalle = " ".join(detalle.split())[:300]
        mensaje = f"{proveedor} respondió HTTP {respuesta.status_code}."
        if detalle:
            mensaje += f" Detalle: {detalle}"
        raise ErrorDeInterpretacion(mensaje)

    try:
        return respuesta.json()
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ErrorDeInterpretacion(
            f"{proveedor} respondió con un JSON inválido."
        ) from error


def _solicitar_gemini(api_key, prompt, esquema):
    if not api_key.isascii() or any(caracter.isspace() for caracter in api_key):
        raise ErrorDeInterpretacion("GEMINI_API_KEY contiene caracteres no válidos.")
    modelo = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    respuesta = _pedir_json(
        "Gemini",
        url,
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": esquema,
                "temperature": 0,
            },
        },
        params={"key": api_key},
    )
    try:
        contenido = respuesta["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(contenido)["items"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ErrorDeInterpretacion(
            "Gemini respondió, pero su respuesta no tuvo el formato esperado."
        ) from error


def _solicitar_groq(api_key, prompt):
    if not api_key.isascii() or any(caracter.isspace() for caracter in api_key):
        raise ErrorDeInterpretacion("GROQ_API_KEY contiene caracteres no válidos.")
    modelo = os.environ.get("GROQ_MODEL", MODELO_GROQ_PREDETERMINADO)
    respuesta = _pedir_json(
        "Groq",
        URL_GROQ,
        {
            "model": modelo,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un intérprete de instrucciones de compra. Responde únicamente "
                        "con un objeto JSON que contenga la propiedad items. Cada elemento "
                        "debe tener sku (entero), proveedor (texto o null) y cantidad "
                        "(entero o null). No inventes productos ni proveedores."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        contenido = respuesta["choices"][0]["message"]["content"]
        return json.loads(contenido)["items"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ErrorDeInterpretacion(
            "Groq respondió, pero su respuesta no tuvo el formato esperado."
        ) from error


def _solicitar_seleccion(instruccion, criticos):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    if not gemini_key and not groq_key:
        raise ErrorDeInterpretacion(
            "Configura GEMINI_API_KEY o GROQ_API_KEY en .env para usar el intérprete."
        )

    prompt, esquema = _preparar_prompt(instruccion, criticos)
    error_gemini = None
    if gemini_key:
        try:
            return _solicitar_gemini(gemini_key, prompt, esquema)
        except ErrorDeInterpretacion as error:
            error_gemini = error

    if groq_key:
        try:
            return _solicitar_groq(groq_key, prompt)
        except ErrorDeInterpretacion as error_groq:
            if error_gemini:
                raise ErrorDeInterpretacion(
                    f"Gemini no estuvo disponible ({error_gemini}). "
                    f"Groq tampoco pudo interpretar la instrucción ({error_groq})."
                ) from error_groq
            raise

    raise ErrorDeInterpretacion(
        f"Gemini no pudo interpretar la instrucción ({error_gemini}). "
        "Configura GROQ_API_KEY en .env para habilitar el respaldo."
    ) from error_gemini


def seleccionar_productos(instruccion, criticos):
    """Devuelve solo los productos pedidos, con proveedor y cantidad validados."""
    if not instruccion.strip():
        raise ErrorDeInterpretacion("Escribe qué productos quieres pedir.")
    if not criticos:
        raise ErrorDeInterpretacion("No hay productos con proveedor para seleccionar.")

    solicitados = _solicitar_seleccion(instruccion, criticos)
    if not solicitados:
        raise ErrorDeInterpretacion(
            "No pude identificar productos concretos. Indica el nombre del producto "
            "o su SKU, y opcionalmente proveedor y unidades."
        )

    por_sku = {c["sku"]: c for c in criticos}
    seleccionados = []
    vistos = set()
    ajustes = []
    for solicitud in solicitados:
        if not isinstance(solicitud, dict):
            raise ErrorDeInterpretacion("Gemini devolvió una selección inválida.")
        sku = solicitud.get("sku")
        if isinstance(sku, bool) or not isinstance(sku, int) or sku not in por_sku:
            raise ErrorDeInterpretacion(f"El SKU {sku!r} no está entre los productos disponibles.")
        if sku in vistos:
            raise ErrorDeInterpretacion(f"El producto {sku} apareció más de una vez.")
        vistos.add(sku)

        original = por_sku[sku]
        proveedor = solicitud.get("proveedor") or original["recomendada"]["proveedor"]
        opcion = next((o for o in original["opciones"] if o["proveedor"] == proveedor), None)
        if opcion is None:
            disponibles = ", ".join(o["proveedor"] for o in original["opciones"])
            raise ErrorDeInterpretacion(
                f"{proveedor!r} no surte "
                f"{original.get('titulo', original.get('titulo_producto', sku))}. "
                f"Proveedores disponibles: {disponibles}."
            )

        cantidad = solicitud.get("cantidad")
        if cantidad is None:
            cantidad_final = opcion["cantidad_a_pedir"]
        else:
            if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
                raise ErrorDeInterpretacion("Las unidades deben ser un número entero mayor que cero.")
            empaque = opcion["empaque"]
            cantidad_final = (
                math.ceil(max(cantidad, opcion["pedido_minimo_unidades"]) / empaque) * empaque
            )
            if cantidad_final != cantidad:
                ajustes.append(
                    f"{original.get('titulo', original.get('titulo_producto', sku))}: "
                    f"pediste {cantidad}; el empaque y mínimo del proveedor "
                    f"requieren {cantidad_final} unidades."
                )

        seleccion = {**original, "seleccionada": {
            **opcion,
            "cantidad_a_pedir": cantidad_final,
            "total_cop": cantidad_final * opcion["precio_unitario_cop"],
        }}
        seleccionados.append(seleccion)

    return seleccionados, ajustes
