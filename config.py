# config.py
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENPIPE_API_KEY = os.getenv('OPENPIPE_API_KEY')
OPENPIPE_API_KEY_EXPENSIVE = os.getenv('OPENPIPE_API_KEY_EXPENSIVE')

# Validate environment variables
if not DISCORD_TOKEN:
    raise EnvironmentError("Missing DISCORD_TOKEN in environment variables.")
if not OPENPIPE_API_KEY:
    raise EnvironmentError("Missing OPENPIPE_API_KEY in environment variables.")
if not OPENPIPE_API_KEY_EXPENSIVE:
    raise EnvironmentError("Missing OPENPIPE_API_KEY_EXPENSIVE in environment variables.")

# Set up logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logger = logging.getLogger('sydney_bot')
logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

# File Handler with Rotation
file_handler = RotatingFileHandler('logs/sydney_bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
file_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)