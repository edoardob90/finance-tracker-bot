"""
Bot's functions for the `/summary` command
"""
import logging
from constants import *
from telegram import (
    Update,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler
)

def start(update: Update, context: CallbackContext) -> int:
    """Ask for a summary"""
    update.message.reply_text("This is currently not implemented, sorry :-(")
    return ConversationHandler.END