import os
import json
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اكتب /quiz لبدء الاختبار 🎯")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    quiz_state[chat_id] = {"i": 0}
    await send_question(chat_id, context)

async def send_question(chat_id, context):
    i = quiz_state[chat_id]["i"]

    if i >= len(QUESTIONS):
        await context.bot.send_message(chat_id, "🏁 انتهى الاختبار")
        return

    q = QUESTIONS[i]

    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["answer"],
        open_period=20,
        is_anonymous=False
    )

    await asyncio.sleep(21)
    quiz_state[chat_id]["i"] += 1
    await send_question(chat_id, context)

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.run_polling()

if __name__ == "__main__":
    main()
