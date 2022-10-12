# pylint: disable=anomalous-backslash-in-string
"""
Bot's functions for the `/summary` command
"""
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler

from constants import LOG_FORMAT

# Env variables
load_dotenv()
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Enable logging
logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def not_implemented(update: Update, context: CallbackContext) -> int:
    """Ask for a summary"""
    update.message.reply_text(
        "Sorry, this function is currently not yet implemented 😞 Hopefully, it will be soon\. Bye 👋"
    )
    return ConversationHandler.END
