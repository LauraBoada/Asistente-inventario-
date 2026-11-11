import json
import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr


def preparar_envio(aprobacion: dict) -> dict:
    modo = os.getenv("MODO_ENVIO_PEDIDOS", "simulado").strip().lower()
    if modo == "simulado":
        return {"modo": modo, "mensaje": None, "destinatario": None}
    if modo != "gmail":
        raise ValueError("MODO_ENVIO_PEDIDOS debe ser 'simulado' o 'gmail'")

    remitente = os.getenv("GMAIL_USER", "").strip()
    clave_aplicacion = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    destinatarios_json = os.getenv("GMAIL_DESTINATARIOS", "{}")
    if not remitente or not clave_aplicacion:
        raise ValueError("Configura GMAIL_USER y GMAIL_APP_PASSWORD para enviar por Gmail")
    if parseaddr(remitente)[1] != remitente or "@" not in remitente:
        raise ValueError("GMAIL_USER debe ser una dirección de correo válida")

    try:
        destinatarios = json.loads(destinatarios_json)
    except json.JSONDecodeError as error:
        raise ValueError("GMAIL_DESTINATARIOS debe ser un objeto JSON válido") from error
    if not isinstance(destinatarios, dict):
        raise ValueError("GMAIL_DESTINATARIOS debe ser un objeto JSON")

    destinatario = destinatarios.get(aprobacion["proveedor"], "")
    if not isinstance(destinatario, str):
        raise ValueError(f"No hay un correo válido configurado para {aprobacion['proveedor']}")
    destinatario = destinatario.strip()
    direccion = parseaddr(destinatario)[1]
    if not direccion or direccion != destinatario or "@" not in direccion:
        raise ValueError(f"No hay un correo válido configurado para {aprobacion['proveedor']}")

    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = f"Solicitud de pedido - SKU {aprobacion['sku']}"
    nombre_producto = aprobacion.get("titulo_producto") or f"SKU {aprobacion['sku']}"
    mensaje.set_content(
        "Hola,\n\n"
        "Solicitamos cotizar y despachar el siguiente pedido:\n"
        f"Producto: {nombre_producto}\n"
        f"SKU: {aprobacion['sku']}\n"
        f"Cantidad: {aprobacion['cantidad']} unidades\n"
        f"Total cotizado: ${aprobacion['total_cop']:,.0f} COP\n\n"
        "Este pedido fue aprobado por el responsable de la tienda.\n"
        "Por favor, confirma disponibilidad y fecha estimada de entrega.\n"
    )
    return {
        "modo": modo,
        "mensaje": mensaje,
        "destinatario": destinatario,
        "remitente": remitente,
        "clave_aplicacion": clave_aplicacion,
    }


def ejecutar_envio(preparacion: dict) -> dict:
    if preparacion["modo"] == "simulado":
        return {"estado": "simulado_enviado", "destinatario": None}

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
        servidor.login(preparacion["remitente"], preparacion["clave_aplicacion"])
        rechazados = servidor.send_message(preparacion["mensaje"])
    if rechazados:
        raise smtplib.SMTPRecipientsRefused(rechazados)
    return {"estado": "enviado", "destinatario": preparacion["destinatario"]}