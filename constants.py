"""
Constants
"""
import os
from os.path import join, dirname, exists
from dotenv import load_dotenv

load_dotenv()

# Logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_level = os.environ.get("LOG_LEVEL", "INFO")

# The three conversation states:
# CHOOSING = 0
# CHOICE = 1
# REPLY = 2
CHOOSING, CHOICE, REPLY = range(3)

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