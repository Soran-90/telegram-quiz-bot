import json
import asyncio
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

BOT_TOKEN = "8105573215:AAH5HOerr48DVo40WZRYYBe2OIe8fdeSnK4"
QUIZ_TIME = 20  # seconds

# تحميل الأسئلة
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_running = False
current_question = 0
scores = defaultdict(int)
answer_times = defaultdict(float)


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_running, current_question, scores, answer_times

    if quiz_running:
        await update.message.reply_text("⚠️ الكوز شغال حالياً.")
        return

    quiz_running = True
    current_question = 0
    scores.clear()
    answer_times.clear()

    await update.message.reply_text("🎯 بدأ الكوز! استعدوا...")

    await send_question(update, context)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_question, quiz_running

    if current_question >= len(QUESTIONS):
        await show_results(update, context)
        quiz_running = False
        return

    q = QUESTIONS[current_question]

    poll_message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"❓ سؤال {current_question + 1}/{len(QUESTIONS)}\n\n{q['question']}",
        options=[
            f"A) {q['options'][0]}",
            f"B) {q['options'][1]}",
            f"C) {q['options'][2]}",
            f"D) {q['options'][3]}",
        ],
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False,
        open_period=QUIZ_TIME,
    )

    context.chat_data["poll_id"] = poll_message.poll.id
    context.chat_data["start_time"] = time.time()

    await asyncio.sleep(QUIZ_TIME + 1)

    current_question += 1
    await send_question(update, context)


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user = answer.user

    if answer.poll_id != context.chat_data.get("poll_id"):
        return

    start_time = context.chat_data.get("start_time")
    if start_time:
        answer_times[user.full_name] += time.time() - start_time

    if answer.option_ids:
        scores[user.full_name] += 1


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("❌ لم يشارك أحد.")
        return

    sorted_users = sorted(
        scores.items(),
        key=lambda x: (-x[1], answer_times[x[0]])
    )

    text = "🏁 **انتهى الكوز!**\n\n🏆 **Top 10:**\n"
    for i, (user, score) in enumerate(sorted_users[:10], start=1):
        text += f"{i}. {user} — {score} إجابة صحيحة\n"

    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(PollAnswerHandler(poll_answer_handler))
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🤖 Quiz Bot Ready")))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
