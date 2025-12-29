import json
import time
import asyncio
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

# ================= CONFIG =================
BOT_TOKEN = "8105573215:AAH5HOerr48DVo40WZRYYBe2OIe8fdeSnK4"  # أو استخدم env
QUIZ_TIME = 20  # seconds
# ==========================================

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_running = False
current_question = 0

scores = defaultdict(int)
answer_times = defaultdict(float)

# ==========================================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    admins = await context.bot.get_chat_administrators(chat_id)
    return any(a.user.id == user_id for a in admins)

# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Quiz Bot Ready\nاكتب /quiz لبدء الاختبار")

# ==========================================

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_running, current_question, scores, answer_times

    if not await is_admin(update, context):
        await update.message.reply_text("❌ الأمر مخصص للأدمن فقط")
        return

    if quiz_running:
        await update.message.reply_text("⚠️ يوجد كوز شغال حالياً")
        return

    quiz_running = True
    current_question = 0
    scores.clear()
    answer_times.clear()

    await update.message.reply_text("🎯 بدأ الكوز!\nاستعدوا...")
    await send_question(update, context)

# ==========================================

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_question, quiz_running

    if current_question >= len(QUESTIONS):
        await show_results(update, context)
        quiz_running = False
        return

    q = QUESTIONS[current_question]

    poll_message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"❓ سؤال {current_question+1}/{len(QUESTIONS)}\n\n{q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False,
        open_period=QUIZ_TIME,
    )

    context.chat_data["poll_id"] = poll_message.poll.id
    context.chat_data["poll_start"] = time.time()

    await asyncio.sleep(QUIZ_TIME + 1)

    current_question += 1
    await send_question(update, context)

# ==========================================

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user = poll_answer.user
    poll_id = poll_answer.poll_id

    if poll_id != context.chat_data.get("poll_id"):
        return

    start_time = context.chat_data.get("poll_start")
    if not start_time:
        return

    elapsed = time.time() - start_time
    answer_times[user.full_name] += elapsed
    scores[user.full_name] += 1

# ==========================================

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("❌ لم يشارك أحد")
        return

    ranked = sorted(
        scores.items(),
        key=lambda x: (-x[1], answer_times[x[0]])
    )

    text = "🏁 **انتهى الكوز!**\n\n🏆 **أفضل 10:**\n"
    for i, (name, score) in enumerate(ranked[:10], start=1):
        text += f"{i}. {name} — {score} ✔️\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ==========================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(PollAnswerHandler(poll_answer))

    app.run_polling()

# ==========================================

if __name__ == "__main__":
    main()
