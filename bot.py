import json
import asyncio
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = "PUT_YOUR_TOKEN_HERE"

QUIZ_TIME = 20  # seconds

# تحميل الأسئلة
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_running = False
current_question = 0
scores = defaultdict(int)
answer_times = defaultdict(float)


def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    admins = context.bot.get_chat_administrators(chat_id)
    return any(admin.user.id == user_id for admin in admins)


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_running, current_question, scores, answer_times

    if not await is_admin(update, context):
        await update.message.reply_text("❌ هذا الأمر مخصص للأدمن فقط.")
        return

    if quiz_running:
        await update.message.reply_text("⚠️ يوجد كوز شغال حالياً.")
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

    message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"❓ سؤال {current_question + 1}/{len(QUESTIONS)}\n\n{q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False,
        open_period=QUIZ_TIME,
    )

    # حفظ وقت الإرسال
    context.chat_data["poll_start"] = time.time()
    context.chat_data["poll_id"] = message.poll.id

    await asyncio.sleep(QUIZ_TIME + 1)

    current_question += 1
    await send_question(update, context)


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("❌ لم يشارك أحد بالكوز.")
        return

    sorted_users = sorted(
        scores.items(),
        key=lambda x: (-x[1], answer_times[x[0]])
    )

    text = "🏁 **انتهى الكوز!**\n\n🏆 **Top 10:**\n"
    for i, (user, score) in enumerate(sorted_users[:10], start=1):
        text += f"{i}. {user} — {score} إجابة صحيحة\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user = poll_answer.user
    poll_id = poll_answer.poll_id

    if poll_id != context.chat_data.get("poll_id"):
        return

    start_time = context.chat_data.get("poll_start")
    if start_time:
        answer_times[user.first_name] += time.time() - start_time

    scores[user.first_name] += 1


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(
        CommandHandler("start", lambda u, c: u.message.reply_text("🤖 Quiz Bot Ready"))
    )
    app.add_handler(
        telegram.ext.PollAnswerHandler(poll_answer)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
