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
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

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


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("revisar", revisar))
    app.add_handler(CallbackQueryHandler(manejar_respuesta))
    logger.info("Bot de inventario escuchando…")
    app.run_polling()


if __name__ == "__main__":
    main()
