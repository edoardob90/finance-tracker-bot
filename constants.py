"""
Constants
"""
import os
from os.path import join, dirname, exists
from dotenv import load_dotenv
from telegram.ext import ConversationHandler

load_dotenv()

# Logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_level = os.environ.get("LOG_LEVEL", "INFO")

# Currencies supported
CURRENCIES = dict(
    (
        ('E', 'EUR'),
        ('€', 'EUR'),
        ('U', 'USD'),
        ('$', 'USD'),
        ('C', 'CHF'),
        ('G', 'GPB'),
        ('£', 'GPB'),
    )
)

# Path to Google API client secret file
CREDS = os.environ.get("CREDS_FILE", join(dirname(__file__), "credentials.json"))

# TODO: this is *temporary* until I have the app approved by Google
SERVICE_ACCOUNT = bool(os.environ.get("SERVICE_ACCOUNT", False))
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", join(dirname(__file__), "service_account.json"))

# Path to bot's local storage
DATA_DIR = os.environ.get("DATA_DIR", join(dirname(__file__), "storage"))
# Create DATA_DIR if it doesn't exist
if not exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# Variables related to the getUpdates mechanism: 'polling' (default) or 'webhook'
MODE = os.environ.get("MODE", "polling")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", None)
PORT = int(os.environ.get("PORT", "5000"))
LISTEN_URL = os.environ.get("LISTEN_URL", "127.0.0.1")

# Shortcut to end a conversation
END = ConversationHandler.END