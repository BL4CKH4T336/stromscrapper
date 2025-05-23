import requests
import random
import time
from telegram import Bot, InputMediaPhoto, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.error import TelegramError
from datetime import datetime
import os
from flask import Flask, request

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8062649272:AAFkPK3avG4EtjIZKuut8dgq0cv1_F3aihA')
CHANNEL_ID = os.getenv('CHANNEL_ID', '-1002641339979')  # or CHANNEL_ID if numeric
IMAGE_URL = os.getenv('IMAGE_URL', 'https://ibb.co/DXrGXMz')  # Set your image URL here
RAW_FILE_URL = os.getenv('RAW_FILE_URL', 'https://raw.githubusercontent.com/BL4CKH4T336/num/refs/heads/main/vbvbin.txt')
CC_GENERATOR_URL = os.getenv('CC_GENERATOR_URL', 'https://drlabapis.onrender.com/api/ccgenerator?bin={bin}&count=1')
XCHECKER_URL = os.getenv('XCHECKER_URL', 'https://xchecker.cc/api.php?cc={cc}')
BIN_LOOKUP_URL = os.getenv('BIN_LOOKUP_URL', 'https://bins.antipublic.cc/bins/{bin}')
PORT = int(os.getenv('PORT', 10000))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Set this in Render environment variables

# Initialize Flask app for webhook
app = Flask(__name__)

# Initialize bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def get_3d_false_bins():
    try:
        response = requests.get(RAW_FILE_URL)
        response.raise_for_status()
        lines = response.text.split('\n')

        false_bins = []
        for line in lines:
            if "3D FALSE" in line and "✅" in line:
                bin_part = line.split('|')[0].strip()
                if len(bin_part) >= 6:  # Ensure it's a valid BIN
                    false_bins.append(bin_part[:6])  # Take first 6 digits
                    status_text = line.split('|')[-1].strip()

        return false_bins, status_text
    except Exception as e:
        print(f"Error getting 3D false bins: {e}")
        return [], ""

def generate_cc(bin):
    try:
        response = requests.get(CC_GENERATOR_URL.format(bin=bin))
        response.raise_for_status()
        return response.text.strip()  # Assuming the response is plain text CC
    except Exception as e:
        print(f"Error generating CC: {e}")
        return None

def check_cc(cc):
    try:
        response = requests.get(XCHECKER_URL.format(cc=cc))
        response.raise_for_status()
        data = response.json()
        return data.get('details', '').split('\n')[0]  # Get first line of details
    except Exception as e:
        print(f"Error checking CC: {e}")
        return "Check failed"

def get_bin_info(bin):
    try:
        response = requests.get(BIN_LOOKUP_URL.format(bin=bin))
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting BIN info: {e}")
        return {}

def format_message(cc, auth_response, bin_status, bin_info):
    # Extract CC components
    cc_parts = cc.split('|')
    cc_number = cc_parts[0]
    month = cc_parts[1] if len(cc_parts) > 1 else 'XX'
    year = cc_parts[2] if len(cc_parts) > 2 else 'XXXX'
    cvv = cc_parts[3] if len(cc_parts) > 3 else 'XXX'

    # Create extrapolated CC
    extrap_cc = f"{cc_number[:12]}xxxx|{month}|{year}"

    # Format BIN info
    brand = bin_info.get('brand', 'UNKNOWN')
    bank = bin_info.get('bank', 'UNKNOWN')
    country = bin_info.get('country_name', 'UNKNOWN')
    flag = bin_info.get('country_flag', '🏳')
    card_type = bin_info.get('type', 'UNKNOWN')

    message = f"""
✜━━━━━━━━━━━━━━━━━━━━✜
[✜] CC: <code>{cc}</code>
[✜] EXTRAP: <code>{extrap_cc}</code>
[✜] CC: <code>{cc_number}</code>
-----------------------------
[✜] Auth : <i>{auth_response}</i>
[✜] 3DS : <i>{bin_status} ✅</i>
-----------------------------
[✜] BIN: #{bin_info.get('bin', '')}
[✜] BANK: {bank}
[✜] DATA: {brand} - {card_type}
[✜] COUNTRY: {country} {flag}
✜━━━━━━━━━━━━━━━━━━━━✜
"""
    return message.strip()

async def send_to_channel(context: CallbackContext):
    try:
        # Get 3D FALSE bins
        false_bins, status_text = get_3d_false_bins()

        if not false_bins:
            print("No 3D FALSE bins found")
            return

        # Select a random BIN
        selected_bin = random.choice(false_bins)

        # Generate CC
        cc = generate_cc(selected_bin)
        if not cc:
            return

        # Check CC
        auth_response = check_cc(cc)

        # Get BIN info
        bin_info = get_bin_info(selected_bin)

        # Format message
        message = format_message(cc, auth_response, status_text, bin_info)

        # Send message with photo
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=IMAGE_URL,
                caption=message,
                parse_mode='HTML'
            )
            print(f"Message sent at {datetime.now()}")
        except TelegramError as e:
            print(f"Error sending message: {e}")

    except Exception as e:
        print(f"Error in send_to_channel: {e}")

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('Bot is running!')

async def setup_bot():
    # Create Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))

    # Set up job queue to send messages periodically
    job_queue = application.job_queue
    job_queue.run_repeating(send_to_channel, interval=180, first=10)

    # Set webhook
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

    # Add webhook handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: None))

    return application

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming Telegram updates via webhook"""
    application = await setup_bot()
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return 'ok'

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    # For local testing without webhook
    import asyncio
    
    async def run_bot():
        application = await setup_bot()
        await application.run_polling()

    # For production with webhook
    app.run(host='0.0.0.0', port=PORT)
