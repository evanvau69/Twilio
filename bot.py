from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from twilio.rest import Client
from keep_alive import keep_alive

import time
from datetime import datetime

# Admin and permission system
ADMIN_IDS = [6165060012]
user_permissions = {6165060012: float("inf")}
user_used_free_plan = set()

# Twilio session data
user_clients = {}
user_available_numbers = {}
user_purchased_numbers = {}

# Time formatting helper
def format_remaining_time(seconds_left):
    minutes, seconds = divmod(int(seconds_left), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    months, weeks = divmod(weeks, 4)

    if months > 0:
        return f"{months} মাস {weeks} সপ্তাহ"
    elif weeks > 0:
        return f"{weeks} সপ্তাহ {days} দিন"
    elif days > 0:
        return f"{days} দিন {hours} ঘন্টা"
    elif hours > 0:
        return f"{hours} ঘন্টা {minutes} মিনিট"
    elif minutes > 0:
        return f"{minutes} মিনিট"
    else:
        return f"{seconds} সেকেন্ড"

# Start command with permission check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    expire_time = user_permissions.get(user_id, 0)
    current_time = time.time()

    if current_time > expire_time:
        keyboard = [
            [InlineKeyboardButton("1 Hour - Free", callback_data="PLAN:1h")],
            [InlineKeyboardButton("1 Day - $2", callback_data="PLAN:1d")],
            [InlineKeyboardButton("7 Day - $10", callback_data="PLAN:7d")],
            [InlineKeyboardButton("15 Day - $15", callback_data="PLAN:15d")],
            [InlineKeyboardButton("30 Day - $20", callback_data="PLAN:30d")],
        ]
        await update.message.reply_text(
            "Bot এর Subscription কিনার জন্য নিচের বাটনে ক্লিক করুন \u2b07\u2b07",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    seconds_left = expire_time - current_time
    time_text = format_remaining_time(seconds_left)
    keyboard = [
        [InlineKeyboardButton(f"তুমি বটটি আর {time_text} চালাতে পারবা 🌸", callback_data="NONE")]
    ]
    await update.message.reply_text(
        "স্বাগতম 🌸 Twilio Work Shop এ 🌺\n\n"
        "/login <SID> <TOKEN>\n"
        "/buy_number <Area Code>\n"
        "/show_messages\n"
        "/delete_number\n"
        "/my_numbers\n"
        "SUPPORT : @EVANHELPING_BOT",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Permission decorator
def permission_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        expire_time = user_permissions.get(user_id, 0)
        if time.time() > expire_time:
            keyboard = [
                [InlineKeyboardButton("1 Hour - Free", callback_data="PLAN:1h")],
                [InlineKeyboardButton("1 Day - $2", callback_data="PLAN:1d")],
                [InlineKeyboardButton("7 Day - $10", callback_data="PLAN:7d")],
                [InlineKeyboardButton("15 Day - $15", callback_data="PLAN:15d")],
                [InlineKeyboardButton("30 Day - $20", callback_data="PLAN:30d")],
            ]
            await (update.message or update.callback_query).reply_text(
                "Bot এর Subscription কিনার জন্য নিচের বাটনে ক্লিক করুন \u2b07\u2b07",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        return await func(update, context)
    return wrapper

# Other command functions
@permission_required
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("ব্যবহার: /login <SID> <AUTH_TOKEN>")
        return
    sid, token = context.args
    try:
        client = Client(sid, token)
        client.api.accounts(sid).fetch()
        user_clients[update.effective_user.id] = client
        await update.message.reply_text("✅ লগইন সফল!")
    except Exception as e:
        await update.message.reply_text(f"লগইন ব্যর্থ: {e}")

# Subscription button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("PLAN:"):
        plan = data.split(":")[1]
        username = f"@{query.from_user.username}" if query.from_user.username else "N/A"

        prices = {
            "1h": (3600, "1 Hour", "$0"),
            "1d": (86400, "1 Day", "$2"),
            "7d": (604800, "7 Day", "$10"),
            "15d": (1296000, "15 Day", "$15"),
            "30d": (2592000, "30 Day", "$20")
        }

        if plan in prices:
            seconds, label, cost = prices[plan]
            msg = (
                f"**Please send {cost} to Binance Pay ID: 469628989**\n\n"
                f"পেমেন্ট করার পর প্রুভ (screenshot/transaction ID) পাঠান: @EVANHELPING_BOT\n\n"
                f"Your payment details:\n"
                f"🆔 User ID: {query.from_user.id}\n"
                f"👤 Username: {username}\n"
                f"📋 Plan: {label}\n"
                f"💰 Amount: {cost}"
            )
            await query.edit_message_text(msg, parse_mode="Markdown")
            return

# Grant command for Admins to give permissions to users
@permission_required
async def grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি এই কমান্ড ব্যবহার করতে পারবেন না।")
        return
    if len(context.args) != 2:
        await update.message.reply_text("ব্যবহার: /grant <user_id> <duration>\nযেমন: /grant 123456789 3d")
        return
    try:
        target_id = int(context.args[0])
        duration = context.args[1].lower()
        if duration.endswith("mo"):
            amount = int(duration[:-2])
            seconds = amount * 2592000
        elif duration[-1] in "mhdw":
            unit = duration[-1]
            amount = int(duration[:-1])
            unit_map = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
            seconds = amount * unit_map[unit]
        else:
            raise ValueError("invalid unit")
        
        user_permissions[target_id] = time.time() + seconds
        await update.message.reply_text(f"✅ {target_id} কে {duration} সময়ের জন্য পারমিশন দেওয়া হয়েছে।")
    except Exception:
        await update.message.reply_text("❌ অবৈধ সময় ইউনিট। ব্যবহার করুন: m, h, d, w, mo")

def main():
    keep_alive()
    TOKEN = "8018963341:AAFBirbNovfFyvlzf_EBDrBsv8qPW5IpIDA"
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grant", grant))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
