import os
from flask import Flask, request
from telegram import Update, ChatInviteLink
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters
)
from datetime import datetime, timedelta
from threading import Thread

# ======== تنظیمات ربات ========
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))

# ======== دیتاست‌ها ========
user_invite_links = {}
invite_counts = {}
mission_completed = set()
invitee_to_inviter = {}
mission_start_time = {}
mission_end_time = {}
extended_users = set()

# ======== ساخت Application ========
application = ApplicationBuilder().token(TOKEN).build()
job_queue = application.job_queue  # JobQueue رو بعد از build استفاده می‌کنیم

# ======== فرمان /start ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ربات با موفقیت راه‌اندازی شد!\n"
        "برای شروع، دستور /link را بزنید."
    )
application.add_handler(CommandHandler("start", start))

# ======== ایجاد لینک اختصاصی ========
async def generate_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_invite_links:
        link = user_invite_links[user_id]
    else:
        try:
            chat_link: ChatInviteLink = await context.bot.create_chat_invite_link(
                chat_id=CHANNEL_ID,
                member_limit=0,
                creates_join_request=False
            )
            link = chat_link.invite_link
            user_invite_links[user_id] = link
            invite_counts[user_id] = 0
            mission_start_time[user_id] = datetime.now()
            mission_end_time[user_id] = datetime.now() + timedelta(days=4)
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ایجاد لینک: {e}")
            return

    msg = (
        f"🎯 سلام! یک ماموریت هیجان‌انگیز واست دارم!\n\n"
        f"کافیه فقط ۱۰ نفر رو با لینک زیر دعوت کنی به کانال 🎉\n\n"
        f"⏳ تا ۳ روز اول تلاش کن، اگه موفق نشدی یه روز اضافه داری 💪\n"
        f"🏆 پس از تکمیل ماموریت، تخفیف ۵۰٪ بهت تعلق می‌گیره!\n\n"
        f"🚀 لینک اختصاصی تو:\n{link}\n\n"
        f"⏱ فقط ۳ روز فرصت داری، پس سریع شروع کن!"
    )
    await update.message.reply_text(msg)

application.add_handler(CommandHandler("link", generate_link))

# ======== وضعیت برای ادمین ========
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی ندارید.")
        return

    in_progress = []
    completed = []

    for uid, link in user_invite_links.items():
        count = invite_counts.get(uid, 0)
        text = f"👤 کاربر: {uid}\n🔗 لینک: {link}\n✅ دعوت موفق: {count}\n"
        if uid in mission_completed:
            completed.append(text)
        else:
            in_progress.append(text)

    response = "💡 **در حال ماموریت:**\n" + ("\n".join(in_progress) if in_progress else "هیچ موردی نیست") + "\n\n"
    response += "🏆 **ماموریت تکمیل شده:**\n" + ("\n".join(completed) if completed else "هیچ موردی نیست")
    await update.message.reply_text(response)

application.add_handler(CommandHandler("status", status))

# ======== ورود عضو جدید ========
async def member_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        user_id = member.id
        inviter_id = invitee_to_inviter.get(user_id)
        if inviter_id and inviter_id not in mission_completed:
            now = datetime.now()
            if now > mission_end_time.get(inviter_id, now):
                await context.bot.send_message(inviter_id, "⏰ مهلت ماموریتت تموم شده! برای فرصت دوباره به ادمین پیام بده 📨")
                continue

            invite_counts[inviter_id] += 1
            count = invite_counts[inviter_id]

            if count < 10:
                await context.bot.send_message(inviter_id, f"🎉 عالیه! یکی دیگه اضافه شد. تعداد دعوت موفق: {count}/10 💪 ادامه بده!")
            elif count == 10:
                mission_completed.add(inviter_id)
                await context.bot.send_message(inviter_id, f"🏆 ترکوندی! ماموریت دعوت ۱۰ نفر کامل شد 🎊\nبرای دریافت جایزه به ادمین پیام بده.")
                await context.bot.send_message(ADMIN_ID, f"✅ کاربر {inviter_id} ماموریت رو تکمیل کرد.")

application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, member_join))

# ======== خروج عضو ========
async def member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.left_chat_member.id
    inviter_id = invitee_to_inviter.get(user_id)
    if inviter_id and inviter_id not in mission_completed:
        invite_counts[inviter_id] -= 1
        await context.bot.send_message(inviter_id, f"⚠️ یک نفر کانال رو ترک کرد. تعداد دعوت موفق شما شد {invite_counts[inviter_id]}.")

application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, member_left))

# ======== بررسی مهلت ماموریت ========
async def check_mission_deadlines(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    for uid, end_time in mission_end_time.items():
        if uid in mission_completed:
            continue
        days_passed = (now - mission_start_time.get(uid, now)).days
        if days_passed == 3 and uid not in extended_users:
            await context.bot.send_message(uid, "⏳ تلاشتو کردی، یک روز دیگه فرصت داری! 🌟 ادامه بده و ۱۰ نفر رو دعوت کن.")
            extended_users.add(uid)
        elif now >= end_time:
            await context.bot.send_message(uid, "🛑 مهلت ماموریتت تموم شد! برای تمدید با ادمین پیام بده.")
            mission_completed.add(uid)

job_queue.run_repeating(check_mission_deadlines, interval=3600, first=10)

# ======== تمدید ماموریت ========
async def reactivate_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ فقط ادمین می‌تونه ماموریت رو تمدید کنه.")
        return

    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ لطفا آیدی عددی کاربر رو وارد کن:\nمثال: /reactivate 123456789")
        return

    if target_id not in user_invite_links:
        await update.message.reply_text("❌ همچین کاربری در لیست دعوت‌ها نیست.")
        return

    mission_start_time[target_id] = datetime.now()
    mission_end_time[target_id] = datetime.now() + timedelta(days=3)
    mission_completed.discard(target_id)
    extended_users.discard(target_id)

    await update.message.reply_text(f"✅ ماموریت کاربر {target_id} با موفقیت تمدید شد (۳ روز).")
    await context.bot.send_message(target_id, "🚀 ماموریتت تمدید شد! دوباره دست به کار شو 💪")

application.add_handler(CommandHandler("reactivate", reactivate_mission))

# ======== وبهوک ========
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok", 200

@app.route("/")
def index():
    return "Bot is running ✅", 200

# ======== اجرای Flask و PTB ========
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    application.run_polling()
