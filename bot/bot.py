# Bot de Telegram: presenta la cotización de cada producto crítico y recibe la respuesta
# del dueño (Agente Interacción). No decide nada por su cuenta: solo llama al grafo
# (grafo.coordinador) para arrancar la revisión y para reanudarla con la decisión del
# dueño; el grafo es quien calcula, pausa y manda a mcp-pedidos.
#
# Ejecutar: python -m bot.bot
# Requiere TELEGRAM_BOT_TOKEN en el .env (igual que MONGODB_URI, nunca se sube a Git).
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.interprete import interpretar_instruccion
from bot.mensajes import botones_cotizacion, decision_desde_callback, formatear_cotizacion, formatear_resumen
from grafo.coordinador import construir_grafo
from grafo.estado import estado_inicial

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot-inventario")

_grafo = None


def _obtener_grafo():
    """Compila el grafo una sola vez por proceso (usa memoria; cambiar por
    construir_checkpointer_mongo() cuando el bot corra junto a un Mongo accesible)."""
    global _grafo
    if _grafo is None:
        _grafo = construir_grafo()
    return _grafo


def _teclado(cotizacion: dict) -> InlineKeyboardMarkup:
    filas = botones_cotizacion(cotizacion)
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(texto, callback_data=data) for texto, data in fila] for fila in filas]
    )


async def _presentar_estado(mandar_mensaje, resultado: dict) -> None:
    """Muestra la cotización pendiente, o el resumen si el grafo ya terminó."""
    if "__interrupt__" in resultado:
        cotizacion = resultado["__interrupt__"][0].value
        await mandar_mensaje(formatear_cotizacion(cotizacion), reply_markup=_teclado(cotizacion), parse_mode="Markdown")
    else:
        await mandar_mensaje(formatear_resumen(resultado))


async def revisar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/revisar: arranca una revisión de inventario para este chat."""
    chat_id = update.effective_chat.id
    config = {"configurable": {"thread_id": str(chat_id)}}

    await update.message.reply_text("Revisando el inventario…")
    resultado = await asyncio.to_thread(_obtener_grafo().invoke, estado_inicial(), config)
    await _presentar_estado(update.message.reply_text, resultado)


async def manejar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botón tocado (aprobar un proveedor o rechazar): reanuda el grafo con la decisión."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    chat_id = query.message.chat.id
    config = {"configurable": {"thread_id": str(chat_id)}}
    aprobado_por = query.from_user.full_name
    decision = decision_desde_callback(query.data, aprobado_por)

    resultado = await asyncio.to_thread(_obtener_grafo().invoke, Command(resume=decision), config)
    await _presentar_estado(query.message.reply_text, resultado)


def _cotizacion_pendiente(snapshot) -> dict | None:
    for tarea in snapshot.tasks:
        for interrupcion in tarea.interrupts:
            cotizacion = getattr(interrupcion, "value", None)
            if isinstance(cotizacion, dict) and "opciones" in cotizacion:
                return cotizacion
    return None


async def manejar_instruccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = update.message.text.strip()
    if not texto or len(texto) > 1000:
        await update.message.reply_text("La instrucción está vacía o es demasiado larga. Usa los botones de la cotización.")
        return

    chat_id = update.effective_chat.id
    config = {"configurable": {"thread_id": str(chat_id)}}
    grafo = _obtener_grafo()
    snapshot = await asyncio.to_thread(grafo.get_state, config)
    cotizacion = _cotizacion_pendiente(snapshot)
    if cotizacion is None:
        await update.message.reply_text("No hay una cotización pendiente. Usa /revisar para iniciar una revisión.")
        return

    try:
        resultado_interprete = await asyncio.to_thread(
            interpretar_instruccion,
            texto,
            cotizacion,
            update.effective_user.full_name,
        )
    except Exception:
        logger.exception("No se pudo interpretar la instrucción del chat %s", chat_id)
        await update.message.reply_text(
            "No pude interpretar la instrucción. Puedes decidir con los botones:",
            reply_markup=_teclado(cotizacion),
        )
        return

    decision = resultado_interprete["decision"]
    if decision is None:
        await update.message.reply_text(
            resultado_interprete["aclaracion"],
            reply_markup=_teclado(cotizacion),
        )
        return

    resultado = await asyncio.to_thread(grafo.invoke, Command(resume=decision), config)
    await _presentar_estado(update.message.reply_text, resultado)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("revisar", revisar))
    app.add_handler(CallbackQueryHandler(manejar_respuesta))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_instruccion))
    logger.info("Bot de inventario escuchando…")
    app.run_polling()


if __name__ == "__main__":
    main()
