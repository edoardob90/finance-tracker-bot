"""
Bot functions for `/auth` command.
They handle Google authorization flow and Google sheet setup.
"""
import pathlib
import logging
import json
import re
from typing import Union, Dict, Tuple
import datetime as dtm
from random import randrange

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError, RefreshError

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
)

from constants import *
import utils
import spreadsheet

logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# State definitions
(
    SELECTING_ACTION,
    NEW_LOGIN,
    EDIT_LOGIN,
    SET_SCHEDULE, 
    REPLY,
    INPUT,
    STOPPING,
) = map(chr, range(7))

# Constants for CallbackQuery data
(
    LOGIN,
    SPREADSHEET,
    SCHEDULE,
    SHOW,
    BACK,
    UP_ONE_LEVEL,
    CANCEL,
    SAVE,
    STOP,
    RESET,
    ID,
    SHEET_NAME,
    DEFAULT_SCHEDULE,
    CUSTOM_SCHEDULE,
) = map(chr, range(7, 21))

#
# Inline Keyboards
#
# Entry-point keyboard
# ROW_1 = ('Login', 'Spreadsheet', 'Schedule')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text='👤 Login', callback_data=str(LOGIN)),
        InlineKeyboardButton(text='📊 Spreadsheet', callback_data=str(SPREADSHEET)),
        InlineKeyboardButton(text='📆 Schedule', callback_data=str(SCHEDULE)),
    ],
    [InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL))]
]

# Login keyboard
edit_login_inline_kb = [
    [
       InlineKeyboardButton(text='Reset login', callback_data=str(RESET)),
       InlineKeyboardButton(text='Login status', callback_data=str(SHOW)) 
    ],
    [InlineKeyboardButton(text='Back', callback_data=str(BACK))]
]

# Spreadsheet keyboard
spreadsheet_inline_kb = [
    [ 
        InlineKeyboardButton(text='ID', callback_data=str(ID)),
        InlineKeyboardButton(text='Sheet name', callback_data=str(SHEET_NAME))
    ],
    [InlineKeyboardButton(text='Back', callback_data=str(BACK))]
]
BUTTONS = dict(
    zip(
       (ID, SHEET_NAME),
       ('ID', 'Sheet name')
    )
)

# Schedule keyboard
schedule_inline_kb = [ 
    [ 
        InlineKeyboardButton(text='Default', callback_data=str(DEFAULT_SCHEDULE)),
        InlineKeyboardButton(text='Custom', callback_data=str(CUSTOM_SCHEDULE))
    ],
    [InlineKeyboardButton(text='Back', callback_data=str(BACK))] 
]

# Utility functions

class AuthError(Exception):
    """Exception for an authentication error"""

def oauth(credentials_file: str, token_file: str = None, code: str = None, user_data: Dict = None) -> Tuple[Union[Credentials, None], Union[None, str]]:
    """Start the authorization flow and return a valid token or refresh an expired one"""
    creds = None
    result = None

    logger.info(f'Current auth data: {user_data}')

    # Look up credentials in `user_data` dictionary ...
    if user_data is not None and 'creds' in user_data:
        logger.info("Loading credentials from user_data dict")
        creds = Credentials.from_authorized_user_info(json.loads(user_data['creds']), spreadsheet.SCOPES)
    
    # ... otherwise try to open `token_file`
    elif token_file is not None and pathlib.Path(token_file).exists():
        logger.info("Loading credentials from JSON file")
        creds = Credentials.from_authorized_user_file(token_file, spreadsheet.SCOPES)

    if creds is not None:
        result = 'Credentials loaded from user data or a valid file\.'

    if not creds or not creds.valid:
        logger.info("Creds are invalid")
        if creds and creds.expired and creds.refresh_token:
            logger.info("Creds are expired")
            try:
                creds.refresh(Request())
            except (UserAccessTokenError, RefreshError):
                raise
        else:
            logger.info("New login: starting a new OAuth flow")
            flow = Flow.from_client_secrets_file(
                credentials_file,
                scopes=spreadsheet.SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob')

            if code:
                logger.info("Last OAuth step: fetching the token from the authorization code")
                # We have an authorization code. This code is used to get the
                # access token.
                flow.fetch_token(code=code)
                
                # Get the credentials
                try:
                    creds=flow.credentials
                except ValueError:
                    logger.error("No valid token found in session")
                    raise

                # Store credentials
                creds_stored = False
                # in user_data dict ...
                if user_data is not None:
                    creds_stored = True
                    user_data['creds'] = creds.to_json()

                # ... and to a JSON file `token_file`
                if token_file is not None:
                    creds_stored = True
                    user_data['token_file'] = token_file
                    with pathlib.Path(token_file).open('w') as token:
                        token.write(creds.to_json())

                if creds_stored:
                    result = 'Token has been saved\.'
            else:
                logger.info("OAuth step: asking the user to authorize the app and enter the authorization code")
                # Tell the user to go to the authorization URL to get the authorization code
                auth_url, _ = flow.authorization_url(prompt='consent')
                result = f'Please, go to [this URL]({auth_url}) to request an authorization code\. Send me the code you obtained\.'
    
    return creds, result

def check_auth(auth_data: Dict = None) -> bool:
    """Check if the auth data for a user are valid"""
    if auth_data is None:
        return False
    
    if auth_data.get('auth_is_done'):
        # First, check if credentials have been stored in `user_data` dict
        if 'creds' in auth_data:
            return True
        # Check if a `token_file` has been saved, is a regular file and exists
        if 'token_file' in auth_data:
            token_file = pathlib.Path(auth_data['token_file'])
            if token_file.is_file() and token_file.exists():
                return True
    
    return False

def check_spreadsheet(spreadsheet_data: Dict = None) -> Union[None, Tuple]:
    """Check if the spreadsheet is set and is valid"""
    if spreadsheet_data is None:
        return None
    
    spreadsheet_data['is_set'] = False
    sheet_id, sheet_name = spreadsheet_data.get('id'), spreadsheet_data.get('sheet_name') 
    if sheet_id and sheet_name:
        spreadsheet_data['is_set'] = True
    
    return sheet_id, sheet_name

#
# Handler-related functions
#
def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/settings` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "⚙️ *Settings menu*\nWhat do you want to do?"
    user_data = context.user_data
    
    if user_data.get('start_over'):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_markdown_v2(text=text, reply_markup=keyboard)
    
    user_data['start_over'] = False

    return SELECTING_ACTION

#
# Login functions
#
def start_login(update: Update, context: CallbackContext) -> str:
    """Check user's login data and start a new OAuth flow"""
    user_data = context.user_data
    query = update.callback_query
    query.answer()
    
    # Initialize user data
    if 'auth' not in user_data:
        user_data['auth'] = {}
    
    auth_data = user_data.get('auth')
    
    # Each user must have a unique token file
    if 'token_file' not in auth_data:
        auth_data['token_file'] = f"{DATA_DIR}/auth_{str(query.from_user.id)}.json"

    # Check if the auth step has been already done
    if not check_auth(auth_data):
        # Start the OAuth2 process
        _, result = oauth(
            credentials_file=CREDS,
            token_file=auth_data['token_file'],
            user_data=auth_data
        )
        query.edit_message_text(text=result)
        return NEW_LOGIN
    else:
        query.edit_message_text(
            "You already logged in\. What do you want to do?",
            reply_markup=InlineKeyboardMarkup(edit_login_inline_kb)
        )
        return EDIT_LOGIN

def store_auth_code(update: Update, context: CallbackContext) -> int:
    """Handle the authorization code of a new login"""
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(END)))
    
    auth_data = context.user_data.get('auth')
    code = update.message.text
    creds, result = oauth(
        credentials_file=CREDS,
        token_file=auth_data['token_file'],
        user_data=auth_data,
        code=code
    )
    
    if creds and result:
        auth_data['auth_is_done'] = True
        update.message.reply_text(text=result, reply_markup=keyboard)
    else:
        auth_data['auth_is_done'] = False
        update.message.reply_text(
            text='⚠️ I could not save your token\!',
            reply_markup=keyboard
        )

    return END

def reset_login(update: Update, context: CallbackContext) -> int:
    """Reset user's login data"""
    auth_data = context.user_data.get('auth')
    # Remove the token file
    pathlib.Path(auth_data['token_file']).unlink(missing_ok=True)
    # Clear the dictionary
    auth_data.clear()
    
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Your login data have been reset\. You can login again from the `/settings` menu\.",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(END)))
    )
    return END

def show_login(update: Update, context: CallbackContext) -> int:
    """Show auth data stored"""
    auth_data = context.user_data.get('auth')
    spreadsheet_data = context.user_data.get('spreadsheet')

    logger.info(f"auth_data: {str(auth_data)}")
    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    auth_data_str = """*Auth status*: {auth_status}

*Spreadsheet*: {ss_status}
    *ID*: {id}
    *Sheet name*: {name}"""

    status = dict.fromkeys(('auth_status', 'ss_status', 'id', 'name'), '❌')
    
    # Check the login
    if check_auth(auth_data):
        status['auth_status'] = '✅'
    
    # Check the spreadsheet
    ss_status = check_spreadsheet(spreadsheet_data)
    if ss_status:
        sheet_id, sheet_name = ss_status
        if None not in (sheet_id, sheet_name):
            status['ss_status'] = '✅'
        status['id'] = utils.escape_markdown(sheet_id or '❌')
        status['name'] = utils.escape_markdown(sheet_name or '❌')

    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Here's your login data:\n\n"
        f"{auth_data_str.format(**status)}\n\n"
        "✅ \= OK\n❌ \= missing data",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(END)))
    )

    return END

#
# Spreadsheet functions
#
def start_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Prompt the spreadsheet menu"""
    # Initialize user data
    user_data = context.user_data
    if 'spreadsheet' not in user_data:
        user_data['spreadsheet'] = {}

    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "Set or reset your spreadsheet:",
        reply_markup=InlineKeyboardMarkup(spreadsheet_inline_kb)
    )
    return INPUT

def prompt_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Prompt which property of a spreadsheet to set/reset"""
    query = update.callback_query
    user_data = context.user_data.get('spreadsheet')

    choice = BUTTONS[query.data]
    user_data['choice'] = choice.lower().replace(' ', '_')
    
    query.answer()
    query.edit_message_text(f"Set the *{choice}* of the spreadsheet")
    
    return REPLY

def set_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Set or reset a spreadsheet property"""
    spreadsheet_data = context.user_data.get('spreadsheet')

    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    data = str(update.message.text)
    choice = str(spreadsheet_data['choice'])
    spreadsheet_data.update({choice: data})
    del spreadsheet_data['choice']

    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    update.message.reply_text(
        f"Done\! Spreadsheet *{choice.upper() if choice == 'id' else choice.replace('_', ' ').capitalize()}* has been set\.",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(UP_ONE_LEVEL)))
    )
    return INPUT

def up_one_level(update: Update, context: CallbackContext) -> int:
    """Go back/up one level"""
    update.callback_query.answer()
    return start_spreadsheet(update, context)

#
# Schedule functions
#
def start_schedule(update: Update, context: CallbackContext) -> str:
    """Prompt the schedule menu"""
    query = update.callback_query
    query.answer()

    # Check if there's a scheduled job to append data
    jobs = context.job_queue.get_jobs_by_name('append_data_' + str(query.from_user.id))
    logger.info(f"Queued jobs: {str(jobs)}")
    next_time = f"{jobs[0].next_t.strftime('%d/%m/%Y, %H:%M')}" if (jobs and jobs[0] is not None) else 'never'
    
    text = f"Your data will be added to the spreadsheet on: *{next_time}*\. Do you want to make a change?"
    query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(schedule_inline_kb))

    return SET_SCHEDULE

def set_default_schedule(update: Update, context: CallbackContext) -> str:
    """Set the default schedule"""
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    utils.remove_job_if_exists('append_data_' + str(user_id), context)
    context.job_queue.run_daily(
        utils.add_to_spreadsheet,
        time=dtm.time(23, 59, randrange(0, 60)),
        context=(user_id, context.user_data),
        name='append_data_' + str(user_id)
    )

    query.edit_message_text(
        "Okay, I will add your data to the spreadsheet *every day at 23:59*\.",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(BACK)))
    )

    return SET_SCHEDULE

def prompt_custom_schedule(update: Update, context: CallbackContext) -> str:
    """Prompt the user to enter a new schedule time/date"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Okay, tell me when you want me to append your data to the spreadsheet\. You can use the following specifications:\n"
        "\- `now`: immediately\n"
        "\- `HH:MM`: today *only* at the specified time \(or tomorrow if time has already passed\)\n"
        "\- `daily HH:MM`: every day at the specified time\n"
        "\- `monthly DD HH:MM`: every month at the specified day and time\n"
    )

    return INPUT

def set_custom_schedule(update: Update, context: CallbackContext) -> str:
    """
    Set a custom schedule
    
    Supported formats:
        - `now`: run once almost immediately
        - `HH:MM`: run once at the specified time
        - `daily HH:MM`: run daily at the specified time
        - `monthly DD HH:MM`: run monthly at the specified day `DD` and time
    """
    when_text = update.message.text
    user_id = update.message.from_user.id
    job_name = f'append_data_{user_id}'
    job_when = None
    
    # Remove any previous job, if any
    utils.remove_job_if_exists(job_name, context)
    
    # Parse the new time/date
    once_pattern = re.compile(r'(now|(?P<hour>\d{2}):(?P<minute>\d{2}))')
    daily_pattern = re.compile(r'(d|daily) (?P<hour>\d{2}):(?P<minute>\d{2})')
    monthly_pattern = re.compile(r'(m|monthly) (?P<day>\d{2}) (?P<hour>\d{2}):(?P<minute>\d{2})')

    # Try the first two time specs
    if ( match := once_pattern.match(when_text) ) is not None:
        hour, minute = match.groupdict().values()
        if not (hour and minute):
            job_when = dtm.datetime.now() + dtm.timedelta(seconds=1)
            when = '*now*'
        else:
            job_when = dtm.time(hour=int(hour), minute=int(minute))
            when = f'*once* at *{hour}:{minute}*'
        
        context.job_queue.run_once(
                utils.add_to_spreadsheet,
                when=job_when,
                context=(user_id, context.user_data),
                name=job_name
            )

        update.message.reply_text(
            f"Your data will be appended {when}",
            reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(BACK)))
        )
        return INPUT
 
    # Try the 3rd and 4th time specs
    if ( match := (daily_pattern.match(when_text) or monthly_pattern.match(when_text)) ) is not None:
        job_when = match.groupdict()
    
    if job_when:
        if 'day' in job_when:
            day = job_when.pop('day')
            context.job_queue.run_monthly(
                utils.add_to_spreadsheet,
                when=dtm.time(**job_when),
                day=day,
                context=(user_id, context.user_data),
                name=job_name
            )
            when = f"on *{day}* every month at *{job_when['hour']}:{job_when['minute']}*"
        else:
            context.job_queue.run_daily(
                utils.add_to_spreadsheet,
                when=dtm.time(**job_when),
                context=(user_id, context.user_data),
                name=job_name
            )
            when = f"every day at *{job_when['hour']}:{job_when['minute']}*"
        
        update.message.reply_text(
            f"Your data will be appended {when}",
            reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(BACK)))
        )
    else:
        update.message.reply_text("⚠️ You entered an invalid time specification\. Try again or use `/cancel` to stop\.")

    return INPUT

#
# Other functions
#
def cancel(update: Update, _: CallbackContext) -> str:
    """Cancel the `settings` command"""
    text = "Use `/settings` to enter the settings or `/help` to know what I can do for you\.\nBye 👋"
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text)
    else:
        update.message.reply_text(text=text)
    return STOPPING

def stop(update: Update, _: CallbackContext) -> int:
    """End the conversation altogether"""
    return utils.stop(command='settings', action='enter your settings', update=update)

def back_to_start(update: Update, context: CallbackContext) -> str:
    """Go back to the start menu"""
    update.callback_query.answer()
    context.user_data['start_over'] = True
    return start(update, context)

# Login conversation handler
login_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_login, pattern=f'^{LOGIN}$')
    ],
    states={
        NEW_LOGIN: [
            MessageHandler(Filters.text & ~Filters.command, store_auth_code)
        ],
        EDIT_LOGIN: [
            CallbackQueryHandler(reset_login, pattern=f'^{RESET}$'),
            CallbackQueryHandler(show_login, pattern=f'^{SHOW}$')
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$'),
        CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="login_second_level",
    persistent=False
)

# Spreadsheet handler
spreadsheet_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_spreadsheet, pattern=f'^{SPREADSHEET}$')
    ],
    states={
        INPUT: [
            CallbackQueryHandler(prompt_spreadsheet, pattern=f'^{ID}$|^{SHEET_NAME}$'),
        ],
        REPLY: [
            MessageHandler(Filters.text & ~Filters.command, set_spreadsheet)
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$'),
        CallbackQueryHandler(up_one_level, pattern=f'^{UP_ONE_LEVEL}$'),
        CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$')
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="spreadsheet_second_level",
    persistent=False
)

# Schedule handler
schedule_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_schedule, pattern=f'^{SCHEDULE}$')
    ],
    states={
        SET_SCHEDULE: [
            CallbackQueryHandler(set_default_schedule, pattern=f'^{DEFAULT_SCHEDULE}$'),
            CallbackQueryHandler(prompt_custom_schedule, pattern=f'^{CUSTOM_SCHEDULE}$'),
        ],
        INPUT: [
            MessageHandler(Filters.text & ~Filters.command, set_custom_schedule),
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$'),
        CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END
    },
    name="schedule_second_level",
    persistent=False
)

# Top-level conversation handler
settings_handler = ConversationHandler(
        entry_points=[
            CommandHandler('settings', start),
        ],
        states={
            SELECTING_ACTION: [
                login_handler,
                spreadsheet_handler,
                schedule_handler,
                CallbackQueryHandler(back_to_start, pattern='^' + str(END) + '$')
            ],
        },
        fallbacks=[
            CommandHandler('stop', stop),
            CallbackQueryHandler(stop, pattern=f'^{CANCEL}$'),
        ],
        name="settings_top_level",
        persistent=False
)
