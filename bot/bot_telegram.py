import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Permite importar las carpetas grafo/, calculo/ y bot/ desde aquí
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

from bot.mensajes import formatear_cotizacion, formatear_resultado
from calculo.proveedores import leer_cotizacion_chat
from grafo.servicio import (
    iniciar_revision, listar_revisiones_pendientes, obtener_revision, responder_revision,
)

load_dotenv(RAIZ / ".env")
logger = logging.getLogger(__name__)
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DUENO = os.environ.get("TELEGRAM_CHAT_ID")      # solo esta persona puede usar el bot


def autorizado(update: Update) -> bool:
    return DUENO is not None and str(update.effective_chat.id) == DUENO


def teclado_revision(thread_id, tiene_sin_proveedor=False):
    filas = [
        [InlineKeyboardButton("✅ Aprobar", callback_data=f"aprobar|{thread_id}"),
         InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar|{thread_id}")],
        [InlineKeyboardButton("✏️ Ajustar productos/proveedor", callback_data=f"ajustar|{thread_id}")],
        [InlineKeyboardButton("⏳ Dejar pendiente", callback_data=f"pendiente|{thread_id}")],
    ]
    if tiene_sin_proveedor:
        filas.append([InlineKeyboardButton(
            "➕ Agregar cotización",
            callback_data=f"cotizacion|{thread_id}",
        )])
    return InlineKeyboardMarkup(filas)


async def enviar_revision(chat_id, thread_id, info, context):
    await context.bot.send_message(
        chat_id=chat_id,
        text=formatear_cotizacion(info),
        reply_markup=teclado_revision(thread_id, bool(info.get("sin_proveedor"))),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = f"Hola 👋 Soy el asistente de inventario.\nTu chat id es: {update.effective_chat.id}"
    if DUENO is None:
        texto += "\nGuárdalo en el archivo .env como TELEGRAM_CHAT_ID y reinicia el bot."
    else:
        texto += "\nEscribe /revisar para revisar el inventario o /pendientes para retomar una revisión."
    await update.message.reply_text(texto)


async def revisar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        await update.message.reply_text("No estás autorizado para usar este bot.")
        return
    await update.message.reply_text("Revisando el inventario… (puede tardar unos segundos)")
    thread_id = datetime.now().strftime("revision-%Y%m%d-%H%M%S-%f")
    try:
        # El grafo es síncrono: se ejecuta en otro hilo para no bloquear al bot
        resultado = await asyncio.to_thread(iniciar_revision, thread_id)
    except Exception as error:
        await update.message.reply_text(f"Ocurrió un error al revisar: {error}")
        return

    if "__interrupt__" not in resultado:
        await update.message.reply_text(formatear_resultado(resultado))
        return

    info = resultado["__interrupt__"][0].value
    await enviar_revision(update.effective_chat.id, thread_id, info, context)


async def pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update):
        await update.message.reply_text("No estás autorizado para usar este bot.")
        return
    try:
        revisiones = await asyncio.to_thread(listar_revisiones_pendientes)
    except Exception as error:
        await update.message.reply_text(f"No pude consultar las revisiones guardadas: {error}")
        return
    if not revisiones:
        await update.message.reply_text("No tienes revisiones pendientes. Escribe /revisar para iniciar una.")
        return
    await update.message.reply_text(f"Tienes {len(revisiones)} revisión(es) pendiente(s):")
    for revision in revisiones:
        thread_id = revision["thread_id"]
        if not revision["recuperable"]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"Revisión {thread_id} no recuperable: quedó guardada con datos "
                    "incompatibles. Inicia una revisión nueva con /revisar."
                ),
            )
            continue
        proveedores = ", ".join(p["proveedor"] for p in revision.get("pedidos", [])) or "ninguno"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"Revisión {thread_id}\n"
                f"Productos: {len(revision.get('criticos', []))} · "
                f"Proveedores: {proveedores}\n"
                f"Sin proveedor: {len(revision.get('sin_proveedor', []))}"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Abrir y responder", callback_data=f"ver|{thread_id}")
            ]]),
        )


async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    consulta = update.callback_query
    await consulta.answer()
    if not autorizado(update):
        return
    try:
        accion, thread_id = consulta.data.split("|", 1)
    except (AttributeError, ValueError):
        await consulta.message.reply_text("Este botón no contiene una acción válida.")
        return

    if accion == "ver":
        try:
            revision = await asyncio.to_thread(obtener_revision, thread_id)
        except Exception as error:
            await consulta.message.reply_text(f"No pude recuperar la revisión: {error}")
            return
        if revision is None:
            await consulta.message.reply_text("La revisión ya no está pendiente.")
            return
        await consulta.edit_message_reply_markup(reply_markup=None)
        await enviar_revision(consulta.message.chat_id, thread_id, revision, context)
        return

    if accion == "cotizacion":
        try:
            revision = await asyncio.to_thread(obtener_revision, thread_id)
        except Exception as error:
            await consulta.message.reply_text(f"No pude cargar la revisión pendiente: {error}")
            return
        if revision is None:
            await consulta.message.reply_text("La revisión ya no está pendiente.")
            return
        skus = revision.get("sin_proveedor", [])
        if not skus:
            await consulta.message.reply_text("Esta revisión no tiene productos pendientes de cotización.")
            return
        context.user_data["revision_cotizacion"] = {
            "thread_id": thread_id,
            "chat_id": consulta.message.chat_id,
            "message_id": consulta.message.message_id,
            "skus": skus,
        }
        context.user_data.pop("revision_ajuste", None)
        await consulta.edit_message_reply_markup(reply_markup=None)
        await consulta.message.reply_text(
            "Envíame la cotización en una sola línea, separada con |:\n"
            "SKU | proveedor | precio unitario COP | días de entrega | pedido mínimo | correo opcional\n"
            f"SKU que necesitan proveedor: {', '.join(str(sku) for sku in skus)}\n"
            "Ejemplo: 486884 | Distribuidora Norte | 12500 | 3 | 12 | pedidos@proveedor.com\n"
            "El precio debe ir sin separadores de miles. El correo es opcional; usa - si no lo tienes."
        )
        return

    if accion == "ajustar":
        context.user_data.pop("revision_cotizacion", None)
        context.user_data["revision_ajuste"] = {
            "thread_id": thread_id,
            "chat_id": consulta.message.chat_id,
            "message_id": consulta.message.message_id,
        }
        await consulta.message.reply_text(
            "Cuéntame qué productos quieres incluir y, si deseas, el proveedor y las unidades. "
            "Por ejemplo: “Incluye la funda azul con Distribuidora Andina, 12 unidades”. "
            "Después podrás revisar la selección y aprobarla, rechazarla o dejarla pendiente."
        )
        return

    if accion not in ("aprobar", "rechazar", "pendiente"):
        await consulta.message.reply_text("La acción de este botón no es válida.")
        return

    await consulta.message.reply_text("Procesando tu respuesta…")
    try:
        resultado = await asyncio.to_thread(responder_revision, thread_id, accion)
    except ValueError as error:
        await consulta.message.reply_text(str(error))
        return
    except Exception as error:
        await consulta.message.reply_text(f"Ocurrió un error: {error}")
        return

    await consulta.edit_message_reply_markup(reply_markup=None)
    if "__interrupt__" in resultado:
        info = resultado["__interrupt__"][0].value
        await enviar_revision(consulta.message.chat_id, thread_id, info, context)
    else:
        await consulta.message.reply_text(formatear_resultado(resultado))


async def recibir_instruccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cotizacion_pendiente = context.user_data.get("revision_cotizacion")
    if cotizacion_pendiente:
        if not autorizado(update):
            await update.message.reply_text("No estás autorizado para usar este bot.")
            return
        try:
            cotizacion = leer_cotizacion_chat(
                update.message.text,
                cotizacion_pendiente["skus"],
            )
        except ValueError as error:
            await update.message.reply_text(str(error))
            return
        await update.message.reply_text("Estoy guardando la cotización y recalculando el inventario…")
        try:
            resultado = await asyncio.to_thread(
                responder_revision,
                cotizacion_pendiente["thread_id"],
                "agregar_cotizacion",
                "Dueño",
                "",
                cotizacion,
            )
        except Exception as error:
            await update.message.reply_text(f"No pude guardar la cotización: {error}")
            return

        context.user_data.pop("revision_cotizacion", None)
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=cotizacion_pendiente["chat_id"],
                message_id=cotizacion_pendiente["message_id"],
                reply_markup=None,
            )
        except BadRequest as error:
            logger.warning("No se pudo retirar el botón de cotización anterior: %s", error)

        if "__interrupt__" in resultado:
            info = resultado["__interrupt__"][0].value
            await enviar_revision(
                update.effective_chat.id,
                cotizacion_pendiente["thread_id"],
                info,
                context,
            )
        else:
            await update.message.reply_text(formatear_resultado(resultado))
        return

    if not context.user_data.get("revision_ajuste"):
        return
    if not autorizado(update):
        await update.message.reply_text("No estás autorizado para usar este bot.")
        return

    ajuste = context.user_data["revision_ajuste"]
    await update.message.reply_text("Estoy revisando tu solicitud y comparando las opciones disponibles…")
    try:
        resultado = await asyncio.to_thread(
            responder_revision,
            ajuste["thread_id"],
            "ajustar",
            "Dueño",
            update.message.text,
        )
    except Exception as error:
        await update.message.reply_text(f"No pude ajustar el pedido: {error}")
        return

    context.user_data.pop("revision_ajuste", None)
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=ajuste["chat_id"],
            message_id=ajuste["message_id"],
            reply_markup=None,
        )
    except BadRequest as error:
        logger.warning("No se pudo retirar el botón del mensaje anterior: %s", error)

    if "__interrupt__" in resultado:
        info = resultado["__interrupt__"][0].value
        await enviar_revision(update.effective_chat.id, ajuste["thread_id"], info, context)
    else:
        await update.message.reply_text(formatear_resultado(resultado))


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("revisar", revisar))
    app.add_handler(CommandHandler("pendientes", pendientes))
    app.add_handler(CallbackQueryHandler(boton))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_instruccion))
    print("Bot en marcha. Escribe /revisar en Telegram. (Ctrl+C para detenerlo)")
    app.run_polling()


if __name__ == "__main__":
    main()