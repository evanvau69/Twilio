import time
from twilio.rest import Client
from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler

# Global variable to store Twilio SID and Auth Token
TWILIO_SID = None
TWILIO_AUTH_TOKEN = None
twilio_client = None

# Global variable to store current number and messages
current_number = None
messages = None

# Telegram Bot Token
TELEGRAM_TOKEN = 'your_telegram_bot_token'

# Puerto Rico Area Codes (All possible area codes)
area_codes = ['787', '939', '340']  # All Puerto Rico area codes

# Function to authenticate Twilio
def authenticate_twilio(sid, auth_token):
    global TWILIO_SID, TWILIO_AUTH_TOKEN, twilio_client
    try:
        twilio_client = Client(sid, auth_token)
        TWILIO_SID = sid
        TWILIO_AUTH_TOKEN = auth_token
        return True
    except Exception as e:
        print(f"Authentication failed: {e}")
        return False

# Function to get account balance
def get_balance():
    account = twilio_client.api.accounts(TWILIO_SID).fetch()
    return account.balance

# Function to buy a new number in Puerto Rico
def buy_new_number():
    global current_number
    for code in area_codes:
        # Try to buy a number from each area code
        available_number = twilio_client.incoming_phone_numbers.create(
            phone_number=f'+1{code}XXXXXXX'  # Puerto Rico number format
        )
        current_number = available_number.phone_number
        break  # Stop after the first number is successfully bought
    return current_number

# Function to delete a number
def delete_number(number):
    twilio_client.incoming_phone_numbers(number).delete()

# Command handler for /start
def start(update, context):
    update.message.reply_text(
        "Welcome to the Twilio Bot! Please login first using /login."
    )

# Command handler for /login
def login(update, context):
    update.message.reply_text("Please send your Twilio SID and Auth Token separated by a space in the format: <sid> <auth_token>")
    return "WAITING_FOR_CREDENTIALS"

# Function to handle SID and Auth Token input
def handle_credentials(update, context):
    user_input = update.message.text.split()
    if len(user_input) != 2:
        update.message.reply_text("Invalid format! Please send your SID and Auth Token separated by a space in the format: <sid> <auth_token>")
        return "WAITING_FOR_CREDENTIALS"

    sid, auth_token = user_input[0], user_input[1]
    
    # Authenticate with Twilio
    if authenticate_twilio(sid, auth_token):
        update.message.reply_text("Logged in successfully! Use /buy to purchase a new number, or /My_Number to view your number.")
        return ConversationHandler.END
    else:
        update.message.reply_text("Login failed! Please check your SID and Auth Token and try again.")
        return "WAITING_FOR_CREDENTIALS"

# Command handler for /buy
def buy(update, context):
    if TWILIO_SID is None or TWILIO_AUTH_TOKEN is None:
        update.message.reply_text("You must log in first using /login.")
        return
    
    global current_number
    # Check if there's an existing number, delete if found
    if current_number:
        delete_number(current_number)
        current_number = None
    
    # Buy a new number
    new_number = buy_new_number()
    
    update.message.reply_text(
        f"Your new number is: {new_number}\n\nYou can use /My_Number to view it again.",
        reply_markup=ReplyKeyboardMarkup(
            [['/My_Number']], one_time_keyboard=True
        )
    )

# Command handler for /My_Number
def my_number(update, context):
    if current_number:
        markup = ReplyKeyboardMarkup([['Message', 'Delete']], one_time_keyboard=True)
        update.message.reply_text(
            f"Your Number: {current_number}", reply_markup=markup
        )
    else:
        update.message.reply_text("No number found! Please use /buy to get a number.")

# Message handling for Delete button
def delete_number_button(update, context):
    global current_number
    if current_number:
        delete_number(current_number)
        current_number = None
        update.message.reply_text("Your number has been deleted.")
    else:
        update.message.reply_text("No number to delete.")

# Message handling for Message button
def show_message_button(update, context):
    if messages:
        update.message.reply_text(f"Your message: {messages}")
    else:
        update.message.reply_text("No messages found.")
        time.sleep(5)  # Wait for 5 seconds
        update.message.reply_text("No messages available.")

# Function to handle incoming SMS from Twilio
def handle_incoming_sms():
    global messages
    messages = "Sample incoming message from Twilio."  # Replace with real-time message fetching from Twilio API

# Main function to set up the bot
def main():
    # Initialize the Application (new approach from v20.0)
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ConversationHandler for login process
    login_handler = ConversationHandler(
        entry_points=[CommandHandler('login', login)],
        states={
            "WAITING_FOR_CREDENTIALS": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials)],
        },
        fallbacks=[],
    )
    
    # Command Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(login_handler)
    application.add_handler(CommandHandler('buy', buy))
    application.add_handler(CommandHandler('My_Number', my_number))
    
    # Callback Handlers for button presses
    application.add_handler(MessageHandler(filters.Regex('^Delete$'), delete_number_button))
    application.add_handler(MessageHandler(filters.Regex('^Message$'), show_message_button))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
