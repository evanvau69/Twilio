from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from twilio.rest import Client
from keep_alive import keep_alive
import time
from datetime import datetime
import asyncio

# Admin and permission system
ADMIN_IDS = [6165060012]  # Admin ID
user_permissions = {6165060012: float("inf")}
user_used_free_plan = set()

# Twilio session data
user_clients = {}
user_available_numbers = {}
user_purchased_numbers = {}

# Check permission decorator
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    expire_time = user_permissions.get(user_id, 0)
    current_time = time.time()

    if current_time < expire_time:
        remaining = int(expire_time - current_time)
        time_left = datetime.utcfromtimestamp(remaining).strftime("%H:%M:%S")
        permission_button = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ আপনি আর {time_left} Bot-টি ব্যবহার করতে পারবেন", callback_data="NONE")],
            [InlineKeyboardButton("Bot Owner : @MR_EVAN3490", url="https://t.me/MR_EVAN3490")],
            [InlineKeyboardButton("SUPPORT : @EVANHELPING_BOT", url="https://t.me/EVANHELPING_BOT")]
        ])
        msg = await update.message.reply_text(
            "স্বাগতম Twilio Work Shop -এ! 🌸", reply_markup=permission_button
        )
        await asyncio.sleep(3)
        await msg.delete()
    else:
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
            [InlineKeyboardButton(text=n.phone_number, callback_data=f"BUY:{n.phone_number}")] for n in numbers
        ] + [[InlineKeyboardButton("Cancel ❌", callback_data="CANCEL")]]
        await update.message.reply_text(
            "নিচের নাম্বারগুলো পাওয়া গেছে:\n\n" + "\n".join(user_available_numbers[user_id]),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await update.message.reply_text(f"সমস্যা: {e}")

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
            [InlineKeyboardButton(text=n.phone_number, callback_data=f"DELETE:{n.phone_number}")] for n in numbers
        ]
        await update.message.reply_text("আপনার নাম্বারগুলো:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"সমস্যা: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("BUY:"):
        phone_number = data.split("BUY:")[1]
        client = user_clients.get(user_id)
        if not client:
            await query.edit_message_text("⚠️ আগে /login করুন।")
            return
        try:
            client.incoming_phone_numbers.create(phone_number=phone_number)
            user_purchased_numbers[user_id] = phone_number
            await query.edit_message_text(f"✅ নাম্বার {phone_number} সফলভাবে কেনা হয়েছে!")
        except Exception as e:
            await query.edit_message_text(f"সমস্যা: {e}")

    elif data == "CANCEL":
        await query.edit_message_text("কোনো নাম্বার কেনা হয়নি।")

    elif data.startswith("PLAN:"):
        plan = data.split("PLAN:")[1]
        if plan == "1h":
            if user_id not in user_used_free_plan:
                user_permissions[user_id] = time.time() + 3600
                user_used_free_plan.add(user_id)
                await query.edit_message_text(f"✅ আপনি ১ ঘণ্টার জন্য Bot ব্যবহার করতে পারবেন।")
            else:
                await query.edit_message_text("❌ আপনি ফ্রি প্ল্যান ব্যবহার করেছেন।")
        else:
            price_map = {
                "1d": 86400,
                "7d": 604800,
                "15d": 1296000,
                "30d": 2592000
            }
            seconds = price_map.get(plan)
            if seconds:
                user_permissions[user_id] = time.time() + seconds
                await query.edit_message_text(f"✅ আপনি {plan} প্ল্যান সফলভাবে কিনেছেন।")
            else:
                await query.edit_message_text("❌ অবৈধ প্ল্যান।")
    else:
        await query.edit_message_text("❌ অবৈধ অপারেশন।")

def main():
    application = Application.builder().token('8018963341:AAFBirbNovfFyvlzf_EBDrBsv8qPW5IpIDA').build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("grant", grant))
    application.add_handler(CommandHandler("buy_number", buy_number))
    application.add_handler(CommandHandler("show_messages", show_messages))
    application.add_handler(CommandHandler("delete_number", delete_number))
    application.add_handler(CommandHandler("my_numbers", my_numbers))
    application.add_handler(CallbackQueryHandler(button_handler))

    keep_alive()
    application.run_polling()

if __name__ == '__main__':
    main()
