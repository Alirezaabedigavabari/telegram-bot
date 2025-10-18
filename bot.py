# bot.py
import os
import json
import logging
from telegram import Update, ChatInviteLink
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
)

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Config from environment ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
ADMIN_ID = os.environ.get("ADMIN_ID")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set. Set the BOT_TOKEN environment variable.")
    raise SystemExit("BOT_TOKEN is required")

try:
    CHANNEL_ID = int(CHANNEL_ID) if CHANNEL_ID is not None else None
except ValueError:
    logger.error("CHANNEL_ID must be an integer (e.g. -1001234567890).")
    raise SystemExit("Invalid CHANNEL_ID")

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID is not None else None
except ValueError:
    logger.error("ADMIN_ID must be an integer (e.g. 8361737480).")
    raise SystemExit("Invalid ADMIN_ID")

# ---------- Files ----------
DATA_FILE = "data.json"
REPORT_FILE = "report.json"

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.exception("Failed to load %s: %s", path, e)
        return {}

def save_json(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.exception("Failed to save %s: %s", path, e)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_json(DATA_FILE)

    if user_id in data:
        await update.message.reply_text(
            f"شما قبلاً لینک اختصاصی دارید:\n{data[user_id]['invite_link']}"
        )
        return

    # create invite link
    try:
        link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=0,
            name=f"link_user_{user_id}"
        )
    except Exception as e:
        logger.exception("create_chat_invite_link failed for user %s: %s", user_id, e)
        await update.message.reply_text(f"خطا در ساخت لینک: {e}")
        return

    data[user_id] = {
        "invite_link": link.invite_link,
        "members": {},  # { "member_id_str": True/False }
        "count": 0,
        "completed": False
    }
    save_json(DATA_FILE, data)

    await update.message.reply_text(
        f"سلام! لینک اختصاصی شما:\n\n{link.invite_link}\n\n"
        "هر کسی با این لینک وارد کانال شود، شمارش می‌شود."
    )
    logger.info("Created invite link for user %s", user_id)


async def member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ChatMemberUpdated handler
    chat_member = update.chat_member
    new_status = chat_member.new_chat_member.status
    invite_link = chat_member.invite_link.invite_link if chat_member.invite_link else None
    user = chat_member.new_chat_member.user
    user_id = str(user.id)

    if not invite_link:
        # join without an invite link (ignore)
        logger.debug("Member %s updated without invite_link; status=%s", user_id, new_status)
        return

    data = load_json(DATA_FILE)
    report = load_json(REPORT_FILE)

    inviter_id = None
    for uid, info in data.items():
        if info.get("invite_link") == invite_link:
            inviter_id = uid
            break

    if not inviter_id:
        logger.info("Invite link used not found in data: %s", invite_link)
        return

    info = data[inviter_id]

    # member joined
    if new_status == "member":
        already = info["members"].get(user_id, False)
        if not already:
            info["members"][user_id] = True
            info["count"] = info.get("count", 0) + 1
            save_json(DATA_FILE, data)

            remaining = max(0, 10 - info["count"])
            if info["count"] < 10:
                await context.bot.send_message(
                    chat_id=int(inviter_id),
                    text=f"{info['count']} نفر از دعوت‌های شما وارد کانال شدند. {remaining} نفر دیگر تا جایزه باقی مانده."
                )
            else:
                if not info.get("completed"):
                    info["completed"] = True
                    save_json(DATA_FILE, data)
                    await context.bot.send_message(
                        chat_id=int(inviter_id),
                        text="تبریک! شما به ۱۰ دعوت موفق رسیدید 🎉"
                    )
                    if ADMIN_ID:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"کاربر {inviter_id} به ۱۰ دعوت موفق رسید."
                        )
                    report[inviter_id] = {"status": "completed", "count": info["count"]}
                    save_json(REPORT_FILE, report)
            logger.info("Inviter %s: count=%d (joined %s)", inviter_id, info["count"], user_id)

    # member left or was kicked
    elif new_status in ("left", "kicked"):
        was_member = info["members"].get(user_id, False)
        if was_member:
            info["members"][user_id] = False
            info["count"] = max(0, info.get("count", 0) - 1)
            save_json(DATA_FILE, data)

            remaining = max(0, 10 - info["count"])
            await context.bot.send_message(
                chat_id=int(inviter_id),
                text=f"{user_id} کانال را ترک کرد. تعداد دعوت‌های موفق شما اکنون: {info['count']}. {remaining} نفر دیگر تا جایزه باقی مانده."
            )
            logger.info("Inviter %s: count=%d (left %s)", inviter_id, info["count"], user_id)

    # else ignore other statuses


# ---------- App setup ----------
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))

if __name__ == "__main__":
    logger.info("Starting bot (Render). CHANNEL_ID=%s ADMIN_ID=%s", CHANNEL_ID, ADMIN_ID)
    app.run_polling()
