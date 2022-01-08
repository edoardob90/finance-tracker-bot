"""
Utils module
"""
from functools import partial
from typing import List, Tuple, Union, Dict, Any
from dateutil.parser import parse
from telegram import InlineKeyboardButton, Update, ParseMode
from telegram.ext import CallbackContext, ConversationHandler
from telegram.utils.helpers import escape_markdown
from constants import *

escape_markdown = partial(escape_markdown, version=2)

def inline_kb_row(buttons: Union[Tuple, List], offset: int = 0) -> List:
    """Build a keyboard row from a list of buttons"""
    _buttons = [{'text': x, 'callback_data': str(y)} for y, x in enumerate(buttons, start=offset)]
    return list(map(lambda x: InlineKeyboardButton(**x), _buttons))

def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def data_to_str(data: Dict[str, Any]) -> str:
    """Build a string concatenating all values in a data `Dict`"""
    facts = [f"*{escape_markdown(key)}:* {escape_markdown(str(value))}" for key, value in data.items()]
    
    return "\n".join(facts)

def parse_data(key: str, value: str, user_data: Dict[str, Any]) -> Dict:
    """Helper function to correctly parse a detail of a new record"""
    if key == 'date':
        user_data['date'] = parse(value, dayfirst=True).strftime("%d/%m/%Y")
    elif key == 'amount':
        try:
            amount, cur = value.split()
        except ValueError:
            # error is raised if no currency is present
            amount = value
            cur = 'X'
        else:
            cur = CURRENCIES[cur[0]] if cur[0] in CURRENCIES else 'X'
        user_data[key] = float(amount)
        user_data['currency'] = cur
    else:
        user_data[key] = str(value)
    
    return user_data

def cancel(update: Update, command: str) -> int:
    """Cancel a command"""
    text = f"Command `/{command}` has been cancelled\. Use `/help` to know about available commands\. Bye\!"
    if update.callback_query:
        update.callback_query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        update.message.reply_markdown_v2(text=text)

    return ConversationHandler.END
