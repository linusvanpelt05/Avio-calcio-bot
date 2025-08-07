
import logging
import keep_alive
keep_alive.keep_alive()
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

SETTIMANE_FILE = "settimane.json"
RPE_FILE = "rpe.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utility

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# /aggiorna_settimana
async def aggiorna_settimana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 3:
        await update.message.reply_text("Usa il formato: /aggiorna_settimana [settimana] [km] [hh:mm]")
        return

    settimana, km_str, ore_str = context.args
    try:
        settimana = str(int(settimana))
        km = float(km_str)
        h, m = map(int, ore_str.split(":"))
    except:
        await update.message.reply_text("Formato non valido. Es: /aggiorna_settimana 2 3.5 00:25")
        return

    data = load_json(SETTIMANE_FILE)
    if settimana not in data:
        data[settimana] = {"km": 0.0, "ore": "00:00"}

    data[settimana]["km"] += km

    old_h, old_m = map(int, data[settimana]["ore"].split(":"))
    total_minutes = (old_h + h) * 60 + (old_m + m)
    new_h = total_minutes // 60
    new_m = total_minutes % 60
    data[settimana]["ore"] = f"{new_h:02}:{new_m:02}"

    save_json(SETTIMANE_FILE, data)
    await update.message.reply_text(f"Aggiornata settimana {settimana}: +{km} km, +{h:02}:{m:02} ore")

# /allenamento_oggi manda tastiera RPE nel gruppo
async def allenamento_oggi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [[InlineKeyboardButton(str(i), callback_data=f"rpe_{i}")] for i in range(1, 11)]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"📅 *Allenamento oggi*\n\nSeleziona il tuo RPE:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    await update.message.reply_text("Allenamento del giorno inviato al canale.")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 Resoconto completo", callback_data="resoconto")],
            [InlineKeyboardButton("📅 Settimane", callback_data="settimane")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📊 Resoconto allenamenti", callback_data="resoconto_privato")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Benvenuto! Per ricevere messaggi privati dal bot, avvialo qui:\n[Avvia il bot](https://t.me/{bot_username})",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# Callback: Resoconto completo per admin
async def callback_resoconto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_json(SETTIMANE_FILE)

    if not data:
        await query.edit_message_text("Nessun dato disponibile al momento.")
        return

    msg = "📊 *Resoconto allenamenti*\n\n"
    for settimana in sorted(data.keys(), key=lambda x: int(x)):
        valori = data[settimana]
        msg += f"Settimana {settimana}: Distanza = {valori['km']:.1f}KM /\nTempo = {valori['ore']}\n"

    await query.edit_message_text(msg, parse_mode="Markdown")

# Callback: Resoconto privato per utenti
async def callback_resoconto_privato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("Controlla i messaggi privati del bot.", show_alert=True)

    data = load_json(SETTIMANE_FILE)
    if not data:
        msg = "Nessun dato disponibile al momento."
    else:
        msg = "📊 *Resoconto allenamenti*\n\n"
        for settimana in sorted(data.keys(), key=lambda x: int(x)):
            valori = data[settimana]
            msg += f"Settimana {settimana}: Distanza = {valori['km']:.1f}KM /\nTempo = {valori['ore']}\n"

    try:
        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
    except:
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}"
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"⚠️ Per ricevere il resoconto in privato, avvia prima il bot: [Avvia il bot]({link})",
            parse_mode="Markdown"
        )

# Callback: Mostra settimane
async def callback_settimane(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_json(SETTIMANE_FILE)

    if not data:
        await query.edit_message_text("Nessuna settimana disponibile.")
        return

    keyboard = [[InlineKeyboardButton(f"Settimana {s}", callback_data=f"settimana_{s}")] for s in sorted(data.keys(), key=int)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📅 Seleziona una settimana:", reply_markup=reply_markup)

# Callback: Dettaglio settimana
async def callback_dettaglio_settimana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    settimana = query.data.replace("settimana_", "")
    data = load_json(SETTIMANE_FILE)

    if settimana not in data:
        await query.edit_message_text("Dati non disponibili.")
        return

    valori = data[settimana]
    msg = f"""📅 *Settimana {settimana}*
Km totali: {valori['km']:.1f}
Ore totali: {valori['ore']}"""
    await query.edit_message_text(msg, parse_mode="Markdown")

# Callback: Risposta RPE - solo invio privato a admin
async def callback_rpe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user.first_name
    rpe_val = query.data.replace("rpe_", "")
    await query.answer("RPE registrato. Grazie!", show_alert=True)

    # Invia messaggio solo all'admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💬 {user} ha selezionato RPE: *{rpe_val}*",
        parse_mode="Markdown"
    )

# Avvio bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aggiorna_settimana", aggiorna_settimana))
    app.add_handler(CommandHandler("allenamento_oggi", allenamento_oggi))
    app.add_handler(CallbackQueryHandler(callback_resoconto, pattern="^resoconto$"))
    app.add_handler(CallbackQueryHandler(callback_resoconto_privato, pattern="^resoconto_privato$"))
    app.add_handler(CallbackQueryHandler(callback_settimane, pattern="^settimane$"))
    app.add_handler(CallbackQueryHandler(callback_dettaglio_settimana, pattern="^settimana_\\d+$"))
    app.add_handler(CallbackQueryHandler(callback_rpe, pattern="^rpe_\\d+$"))

    print("✅ Bot avviato con webhook.")
app.run_webhook(
    listen="0.0.0.0",
    port=8080,
    url_path=TOKEN,
    webhook_url=f"https://avio-calcio-bot.onrender.com/{TOKEN}"
)

