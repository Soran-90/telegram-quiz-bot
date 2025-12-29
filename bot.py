import json
import time
import asyncio
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    ContextTypes,
)

# ================= CONFIG =================
BOT_TOKEN = "8105573215:AAH5HOerr48DVo40WZRYYBe2OIe8fdeSnK4"
QUIZ_TIME = 20  # seconds
# =========================================

# تحميل الأسئلة
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_running = False
current_question_index = 0

scores = defaultdict(int)
total_answer_time = defaultdict(float)

current_poll_id = None
poll_start_time = None


# ---------- Helpers ----------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    admins = await context.bot.get_chat_administrators(chat_id)
    return any(admin.user.id == user_id for admin in admins)


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Quiz Bot جاهز**\n"
        "لبدء الكوز استخدم الأمر:\n"
        "/quiz",
        parse_mode="Markdown",
    )


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_running, current_question_index
    global scores, total_answer_time

    if not await is_admin(update, context):
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
        return

    if quiz_running:
        await update.message.reply_text("⚠️ الكوز شغال حالياً.")
        return

    quiz_running = True
    current_question_index = 0
    scores.clear()
    total_answer_time.clear()

    await update.message.reply_text("🎯 **بدأ الكوز! استعدوا...**")
    await send_question(update, context)


# ---------- Quiz Logic ----------
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_question_index
    global current_poll_id, poll_start_time, quiz_running

    if current_question_index >= len(QUESTIONS):
        await show_results(update, context)
        quiz_running = False
        return

    q = QUESTIONS[current_question_index]

    poll_message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"❓ سؤال {current_question_index + 1}/{len(QUESTIONS)}\n\n{q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False,
        open_period=QUIZ_TIME,
    )

    current_poll_id = poll_message.poll.id
    poll_start_time = time.time()

    await asyncio.sleep(QUIZ_TIME + 1)

    current_question_index += 1
    await send_question(update, context)


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_poll_id, poll_start_time

    if update.poll_answer.poll_id != current_poll_id:
        return

    user = update.poll_answer.user
    elapsed = time.time() - poll_start_time

    scores[user.full_name] += 1
    total_answer_time[user.full_name] += elapsed


# ---------- Results ----------
async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("❌ لم يشارك أحد.")
        return

    ranking = sorted(
        scores.items(),
        key=lambda x: (-x[1], total_answer_time[x[0]])
    )

    text = "🏁 **انتهى الكوز!**\n\n🏆 **أفضل 10:**\n"
    for i, (name, score) in enumerate(ranking[:10], start=1):
        text += f"{i}. {name} — {score} ✅\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    app.run_polling()


if __name__ == "__main__":
    main()
