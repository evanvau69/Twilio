from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from twilio.rest import Client
from keep_alive import keep_alive
import time

# Admin setup
ADMIN_IDS = [6165060012]
user_permissions = {6165060012: float("inf")}
used_free_trial = set()

# Twilio session
user_clients = {}
user_available_numbers = {}
user_purchased_numbers = {}

# Permission decorator
def permission_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        expire_time = user_permissions.get(user_id, 0)
        if time.time() > expire_time:
            keyboard = [
                [InlineKeyboardButton("1 Hour - Free", callback_data="PLAN:1h:0")],
                [InlineKeyboardButton("1 Day - $2", callback_data="PLAN:1d:2")],
                [InlineKeyboardButton("7 Days - $10", callback_data="PLAN:7d:10")],
                [InlineKeyboardButton("15 Days - $15", callback_data="PLAN:15d:15")],
                [InlineKeyboardButton("30 Days - $20", callback_data="PLAN:30d:20")]
            ]
            text = (
                "Bot এর Subscription কিনার জন্য নিচের বাটনে ক্লিক করুন 👇👇\n\n"
                "1 Hour - Free\n1 Day - 2$\n7 Day - 10$\n15 Day - 15$\n30 Day - 20$"
            )
            if update.message:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            elif update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        return await func(update, context)
    return wrapper

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম Evan Bot-এ!\n\n"
        "/login <SID> <TOKEN>\n"
        "/buy_number <Area Code>\n"
        "/show_messages\n"
        "/delete_number\n"
        "/my_numbers\n"
        "SUPPORT : @EVANHELPING_BOT"
    )

# Admin grant command
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

# Subscription button click
async def subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    username = user.username or "N/A"

    data = query.data
    if data.startswith("PLAN:"):
        duration_code, amount = data.split(":")[1:]
        duration_text = {
            "1h": "1 Hour",
            "1d": "1 Day",
            "7d": "7 Days",
            "15d": "15 Days",
            "30d": "30 Days"
        }.get(duration_code, "Unknown")

        if duration_code == "1h" and amount == "0":
            if user_id in used_free_trial:
                await query.edit_message_text("⚠️ আপনি আগেই ১ ঘণ্টার ফ্রি এক্সেস ব্যবহার করেছেন।\n\nদয়া করে অন্য একটি প্ল্যান চয়েস করুন।")
                return
            used_free_trial.add(user_id)
            user_permissions[user_id] = time.time() + 3600
            await query.edit_message_text("✅ আপনার 1 ঘণ্টার ফ্রি এক্সেস অ্যাক্টিভ হয়েছে!\n\nএখন আপনি Bot ব্যবহার করতে পারবেন।")
            return

        message = (
            f"Please send ${amount} to Binance Pay ID: 469628989\n"
            f"After payment, please send proof (screenshot/transaction ID) to the admin @EVANHELPING_BOT\n\n"
            f"Your payment details:\n"
            f"🆔 User ID: {user_id}\n"
            f"👤 Username: {username}\n"
            f"📋 Plan: {duration_text}\n"
            f"💰 Amount: ${amount}\n\n"
            f"Verification must be completed within 15 minutes, or the request will be cancelled."
        )
        await query.edit_message_text(message)

# Login to Twilio
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

# Buy number
@permission_required
async def buy_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("ব্যবহার: /buy_number <Area Code>")
        return
    user_id = update.effective_user.id
    client = user_clients.get(user_id)
    if not client:
        await update.message.reply_text("⚠️ আগে /login করুন।")
        return
    area_code = context.args[0]
    try:
        numbers = client.available_phone_numbers("CA").local.list(area_code=area_code, limit=10)
        if not numbers:
            await update.message.reply_text("নাম্বার পাওয়া যায়নি।")
            return
        user_available_numbers[user_id] = [n.phone_number for n in numbers]
        keyboard = [
            [InlineKeyboardButton(text=n.phone_number, callback_data=f"BUY:{n.phone_number}")]
            for n in numbers
        ]
        await update.message.reply_text(
            "নিচের নাম্বারগুলো পাওয়া গেছে:\n\n" + "\n".join(user_available_numbers[user_id]),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await update.message.reply_text(f"সমস্যা: {e}")

# Show messages
@permission_required
async def show_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = user_clients.get(update.effective_user.id)
    if not client:
        await update.message.reply_text("⚠️ আগে /login করুন।")
        return
    try:
        msgs = client.messages.list(limit=20)
        incoming_msgs = [msg for msg in msgs if msg.direction == "inbound"]
        if not incoming_msgs:
            await update.message.reply_text("কোনো Incoming Message পাওয়া যায়নি।")
            return
        output = "\n\n".join(
            [f"From: {msg.from_}\nTo: {msg.to}\nBody: {msg.body}" for msg in incoming_msgs[:5]]
        )
        await update.message.reply_text(output)
    except Exception as e:
        await update.message.reply_text(f"সমস্যা: {e}")

# Delete number
@permission_required
async def delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = user_clients.get(update.effective_user.id)
    if not client:
        await update.message.reply_text("⚠️ আগে /login করুন।")
        return
    try:
        numbers = client.incoming_phone_numbers.list(limit=1)
        if not numbers:
            await update.message.reply_text("নাম্বার খুঁজে পাওয়া যায়নি।")
            return
        numbers[0].delete()
        await update.message.reply_text("✅ নাম্বার ডিলিট হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"ডিলিট করতে সমস্যা: {e}")

# My numbers
@permission_required
async def my_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = user_clients.get(update.effective_user.id)
    if not client:
        await update.message.reply_text("⚠️ আগে /login করুন।")
        return
    try:
        numbers = client.incoming_phone_numbers.list()
        if not numbers:
            await update.message.reply_text("আপনার কোনো নাম্বার নেই।")
            return
        keyboard = [
            [InlineKeyboardButton(text=n.phone_number, callback_data=f"DELETE:{n.phone_number}")]
            for n in numbers
        ]
        await update.message.reply_text("আপনার নাম্বারগুলো:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"সমস্যা: {e}")

# Buy/Delete button handler
@permission_required
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    client = user_clients.get(user_id)
    if not client:
        await query.edit_message_text("⚠️ আগে /login করুন।")
        return
    data = query.data
    if data.startswith("BUY:"):
        phone_number = data.split("BUY:")[1]
        try:
            purchased = client.incoming_phone_numbers.create(phone_number=phone_number)
            user_purchased_numbers.setdefault(user_id, []).append(purchased.phone_number)
            user_available_numbers[user_id] = []
            await query.edit_message_text(f"✅ আপনি নাম্বারটি কিনেছেন: {purchased.phone_number}")
        except Exception as e:
            await query.edit_message_text(f"নাম্বার কেনা যায়নি: {e}")
    elif data.startswith("DELETE:"):
        phone_number = data.split("DELETE:")[1]
        try:
            numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
            if numbers:
                numbers[0].delete()
                await query.edit_message_text(f"✅ নাম্বার {phone_number} ডিলিট হয়েছে।")
            else:
                await query.edit_message_text("নাম্বার পাওয়া যায়নি।")
        except Exception as e:
            await query.edit_message_text(f"নাম্বার ডিলিট করতে সমস্যা: {e}")

# Main bot runner
def main():
    keep_alive()
    TOKEN = "8018963341:AAFBirbNovfFyvlzf_EBDrBsv8qPW5IpIDA"
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grant", grant))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("buy_number", buy_number))
    app.add_handler(CommandHandler("show_messages", show_messages))
    app.add_handler(CommandHandler("delete_number", delete_number))
    app.add_handler(CommandHandler("my_numbers", my_numbers))

    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(BUY|DELETE):"))
    app.add_handler(CallbackQueryHandler(subscription_handler, pattern="^PLAN:"))

    app.run_polling()

if __name__ == "__main__":
    main()
