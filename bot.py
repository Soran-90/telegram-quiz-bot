import os
import json
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

QUESTIONS_FILE = "questions.json"
QUESTION_TIME = 20  # seconds

with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

sessions = {}


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessions[chat_id] = {
        "index": 0,
        "correct": 0,
    }
    await send_question(chat_id, context)


async def send_question(chat_id, context):
    session = sessions.get(chat_id)
    if not session:
        return

    idx = session["index"]
    if idx >= len(QUESTIONS):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ انتهى الكويز\nإجاباتك الصحيحة: {session['correct']} / {len(QUESTIONS)}"
        )
        sessions.pop(chat_id, None)
        return

    q = QUESTIONS[idx]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["answer"],
        is_anonymous=False,
        open_period=QUESTION_TIME,
    )


async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    chat_id = answer.user.id

    session = sessions.get(chat_id)
    if not session:
        return

    correct = QUESTIONS[session["index"]]["answer"]
    if answer.option_ids and answer.option_ids[0] == correct:
        session["correct"] += 1

    session["index"] += 1
    await send_question(chat_id, context)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(PollAnswerHandler(poll_answer))
    app.run_polling()


if __name__ == "__main__":
    main()
