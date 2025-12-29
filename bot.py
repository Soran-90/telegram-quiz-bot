import os
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

QUESTIONS_FILE = "questions.json"
QUESTION_TIME_SEC = 20


def load_questions() -> List[dict]:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # basic validation
    cleaned = []
    for i, q in enumerate(data):
        if not isinstance(q, dict):
            continue
        if "question" not in q or "options" not in q or "answer" not in q:
            continue
        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            continue
        if not isinstance(q["answer"], int) or q["answer"] not in [0, 1, 2, 3]:
            continue
        cleaned.append(q)

    return cleaned


def abcd_label(idx: int) -> str:
    return ["A", "B", "C", "D"][idx]


@dataclass
class QuizSession:
    questions: List[dict]
    index: int = 0
    score: int = 0

    # current question state
    active: bool = False
    q_message_id: Optional[int] = None
    q_chat_id: Optional[int] = None
    q_start_ts: float = 0.0

    # votes for current question
    votes_count: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    voted_users: Dict[int, int] = field(default_factory=dict)  # user_id -> option idx

    # job name/id
    job_name: Optional[str] = None


# sessions per chat
SESSIONS: Dict[int, QuizSession] = {}


def build_keyboard(options: List[str], qid: str) -> InlineKeyboardMarkup:
    # callback data: "vote|<qid>|<opt>"
    buttons = []
    for i in range(4):
        buttons.append(
            InlineKeyboardButton(
                text=f"{abcd_label(i)}) {options[i]}",
                callback_data=f"vote|{qid}|{i}",
            )
        )
    # 2x2 layout
    keyboard = [
        [buttons[0], buttons[1]],
        [buttons[2], buttons[3]],
    ]
    return InlineKeyboardMarkup(keyboard)


def percent(n: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((n / total) * 100))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "هلا 👋\n"
        "اكتب /quiz حتى نبدي الاختبار.\n"
        "اكتب /stop حتى توقف.\n"
        "اكتب /score حتى تشوف نتيجتك."
    )


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    questions = load_questions()
    if not questions:
        await update.message.reply_text("⚠️ ملف questions.json فارغ/غير صحيح. أضف أسئلة بصيغة صحيحة.")
        return

    # create/reset session
    SESSIONS[chat_id] = QuizSession(questions=questions)
    await update.message.reply_text("✅ تمام! رح نبدي الكوز…")
    await send_next_question(chat_id, context)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sess = SESSIONS.get(chat_id)
    if not sess:
        await update.message.reply_text("ماكو كوز شغال هسه.")
        return

    # cancel job if exists
    if sess.job_name:
        for job in context.job_queue.get_jobs_by_name(sess.job_name):
            job.schedule_removal()

    SESSIONS.pop(chat_id, None)
    await update.message.reply_text("🛑 تم إيقاف الكوز.")


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sess = SESSIONS.get(chat_id)
    if not sess:
        await update.message.reply_text("ماكو كوز شغال. اكتب /quiz.")
        return

    await update.message.reply_text(
        f"📊 نتيجتك الحالية: {sess.score}/{sess.index} "
        f"(باقي {len(sess.questions) - sess.index} سؤال)"
    )


async def send_next_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    sess = SESSIONS.get(chat_id)
    if not sess:
        return

    # finish if reached end
    if sess.index >= len(sess.questions):
        total = len(sess.questions)
        score = sess.score
        pct = int(round((score / total) * 100)) if total else 0

        SESSIONS.pop(chat_id, None)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ خلص الكوز!\n"
                f"🏁 النتيجة النهائية: {score}/{total}\n"
                f"📈 النسبة: {pct}%"
            ),
        )
        return

    q = sess.questions[sess.index]
    sess.active = True
    sess.q_start_ts = time.time()
    sess.votes_count = [0, 0, 0, 0]
    sess.voted_users = {}

    qid = f"{chat_id}:{sess.index}:{int(sess.q_start_ts)}"
    keyboard = build_keyboard(q["options"], qid)

    text = (
        f"❓ سؤال رقم {sess.index + 1}/{len(sess.questions)}\n"
        f"{q['question']}\n\n"
        f"⏳ عندك {QUESTION_TIME_SEC} ثانية للإجابة…"
    )

    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
    sess.q_message_id = msg.message_id
    sess.q_chat_id = chat_id

    # schedule timeout
    sess.job_name = f"timeout_{qid}"
    context.job_queue.run_once(
        quiz_timeout_job,
        when=QUESTION_TIME_SEC,
        data={"chat_id": chat_id, "qid": qid, "q_index": sess.index},
        name=sess.job_name,
    )


async def quiz_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    q_index = data["q_index"]

    sess = SESSIONS.get(chat_id)
    if not sess:
        return

    # if already moved on, ignore
    if sess.index != q_index or not sess.active:
        return

    await close_question_and_show_stats(chat_id, context)
    # move to next
    sess.index += 1
    await send_next_question(chat_id, context)


async def close_question_and_show_stats(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    sess = SESSIONS.get(chat_id)
    if not sess:
        return

    q = sess.questions[sess.index]
    correct = q["answer"]
    total_votes = sum(sess.votes_count)

    lines = []
    for i in range(4):
        p = percent(sess.votes_count[i], total_votes)
        mark = "✅" if i == correct else "▫️"
        lines.append(f"{mark} {abcd_label(i)}: {p}%  ({sess.votes_count[i]})")

    stats_text = "\n".join(lines)

    # announce correct answer
    correct_text = f"{abcd_label(correct)}) {q['options'][correct]}"

    # edit original message to lock answers (remove keyboard)
    if sess.q_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=sess.q_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    # send result summary
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏱ انتهى الوقت!\n"
            f"✅ الجواب الصحيح: {correct_text}\n\n"
            f"📊 نسب الإجابات:\n{stats_text}\n\n"
            f"🏅 نتيجتك الحالية: {sess.score}/{sess.index + 1}"
        ),
    )

    sess.active = False


async def vote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # quick ack

    chat_id = query.message.chat_id
    sess = SESSIONS.get(chat_id)
    if not sess or not sess.active:
        await query.answer("هذا السؤال انتهى.", show_alert=False)
        return

    try:
        prefix, qid, opt_str = query.data.split("|")
        opt = int(opt_str)
    except Exception:
        return

    # ensure vote for current question only
    # (qid contains index+timestamp; we don't strictly parse it, but we can check index)
    current_index = sess.index

    user_id = query.from_user.id

    # prevent double vote (like real quiz)
    if user_id in sess.voted_users:
        await query.answer("✅ أنت جاوبت مسبقًا.", show_alert=False)
        return

    sess.voted_users[user_id] = opt
    sess.votes_count[opt] += 1

    # score: only if correct
    correct = sess.questions[current_index]["answer"]
    if opt == correct:
        sess.score += 1

    await query.answer("تم تسجيل إجابتك ✅", show_alert=False)


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ bot is alive")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Add it as an Environment Variable in Render.")

    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("ping", health))

    app.add_handler(CallbackQueryHandler(vote_handler, pattern=r"^vote\|"))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
