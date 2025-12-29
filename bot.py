import json
import asyncio
import time
from collections import defaultdict

from telegram import Update
from telegram.constants import PollType
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

BOT_TOKEN = "PUT_YOUR_TOKEN_HERE"
QUIZ_TIME = 20  # seconds

# ===== تحميل الأسئلة =====
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

quiz_running = False
current_question = 0

scores = defaultdict(int)
answer_times = defaultdict(float)
poll_correct_answers = {}

# ===== تحقق أدمن =====
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    admins = await context.bot.get_chat_administrators(chat_id)
    return any(admin.user.id == user_id for admin in admins)

# ===== بدء الكوز =====
async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_running, current_question

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
    poll_correct_answers.clear()

    await update.message.reply_text("🎯 بدأ الكوز! استعدوا...")
    await send_question(update, context)

# ===== إرسال سؤال =====
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_question, quiz_running

    if current_question >= len(QUESTIONS):
        quiz_running = False
        await show_results(update, context)
