import os
import json
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

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

QUESTION_TIME = 20
sessions = {}

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessions[chat_id] = {"i": 0, "correct": 0}
    await send_question(chat_id, context)

async def send_question(chat_id, context):
    s = sessions.get(chat_id)
    if not s:
        return

    if s["i"] >= len(QUESTIONS):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ انتهى الكويز\nدرجتك: {s['correct']} / {len(QUESTIONS)}"
        )
        return

    q = QUESTIONS[s["i"]]
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["answer"],
        open_period=QUESTION_TIME,
        is_anonymous=False,
    )

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.poll_answer
    chat_id = ans.user.id
    s = sessions.get(chat_id)
    if not s:
        return

    correct = QUESTIONS[s["i"]]["answer"]
    if ans.option_ids and ans.option_ids[0] == correct:
        s["correct"] += 1

    s["i"] += 1
    await send_question(chat_id, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))
    app.run_polling()

if __name__ == "__main__":
    main()
