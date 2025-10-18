import json
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ChatMemberHandler

BOT_TOKEN = "8155195750:AAEdVGfm3_nKBNRQrgifykgRnw02OZWVPio"
CHANNEL_ID = -1003126728590
ADMIN_ID = 8361737480
DATA_FILE = "data.json"
REPORT_FILE = "report.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_report():
    try:
        with open(REPORT_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_report(report):
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=4)

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        try:
            link: ChatInviteLink = await context.bot.create_chat_invite_link(
                chat_id=CHANNEL_ID,
                member_limit=0,
                name=f"link_user_{user_id}"
            )
        except Exception as e:
            await update.message.reply_text(f"خطا در ساخت لینک: {e}")
            return

        data[user_id] = {
            "invite_link": link.invite_link,
            "members": {},
            "count": 0,
            "completed": False
        }
        save_data(data)
        await update.message.reply_text(
            f"سلام! لینک اختصاصی شما:\n{link.invite_link}"
        )
    else:
        await update.message.reply_text(
            f"شما قبلاً لینک اختصاصی دارید:\n{data[user_id]['invite_link']}"
        )

# ===== ورود و خروج اعضا =====
async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    report = load_report()

    chat_member = update.chat_member
    user_id = str(chat_member.new_chat_member.user.id)
    status = chat_member.new_chat_member.status
    invite_link_used = chat_member.invite_link.invite_link if chat_member.invite_link else None

    if not invite_link_used:
        return

    inviter_id = None
    for uid, info in data.items():
        if info.get("invite_link") == invite_link_used:
            inviter_id = uid
            break

    if not inviter_id:
        return

    info = data[inviter_id]

    if status == "member":
        if user_id not in info["members"] or not info["members"][user_id]:
            info["members"][user_id] = True
            info["count"] += 1
            remaining = max(0, 10 - info["count"])
            if info["count"] < 10:
                await context.bot.send_message(int(inviter_id),
                    f"{info['count']} نفر از دعوت‌های شما وارد کانال شدند. {remaining} نفر دیگر باقی مانده."
                )
            elif info["count"] >= 10 and not info["completed"]:
                info["completed"] = True
                await context.bot.send_message(int(inviter_id), "تبریک! به ۱۰ دعوت موفق رسیدید 🎉")
                await context.bot.send_message(ADMIN_ID, f"کاربر {inviter_id} به ۱۰ دعوت موفق رسید.")
                report[inviter_id] = {"status": "completed", "count": info["count"]}
                save_report(report)

    elif status in ["left", "kicked"]:
        if user_id in info["members"] and info["members"][user_id]:
            info["members"][user_id] = False
            info["count"] -= 1
            remaining = max(0, 10 - info["count"])
            await context.bot.send_message(int(inviter_id),
                f"{user_id} کانال را ترک کرد. تعداد دعوت موفق شما اکنون: {info['count']}. {remaining} نفر دیگر باقی مانده."
            )

    save_data(data)

# ===== اجرای ربات بدون asyncio.run =====
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))

print("ربات در حال اجراست...")
app.run_polling()
