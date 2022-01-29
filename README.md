# Finance Tracker bot

A Telegram bot that helps with your personal finances. It's an experimental and work-in-progress project that provides (or will provide in the future) the following functions:

1. Record an expense/income in a local, persistent storage
2. Connect to a given Google Spreadsheet document via OAuth2
3. Query the data stored in the Google Spreadsheet, e.g., to report monthly summaries or to set alerts on some expense categories

## Setup

## Bot config

The bot requires a few environment variables to be set to work properly. They should be placed in a file called `.env` in the same directory of `finance_tracker_bot.py`.

These are the variables that can be configured:

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | the token of the bot (**required**) as provided by the [BotFather](https://t.me/botfather) |
| `MODE` | either `'polling'` (default) or `'webhook'`. Sets how the bot will interact with Telegram API |
| `WEBHOOK_URL` | if `MODE` is set to `'webhook'`, this is **required**. It's the URL where Telegram should send the POST request upon receiving an update for the bot |
| `PORT` | listen port of the local web server started by `python-telegram-bot` if in webhook mode. Default is `5000` |
| `LISTEN_URL` | URL of the server that will receive webhook requests. By default is `localhost` (`127.0.0.1`) 
| `DEVELOPER_USER_ID` | user ID of a Telegram account where to send error logs and info about exceptions raised while the bot is running (*optional*)
| `CREDS_FILE` | path to the client secred JSON file (see below). Default is `credentials.json` in the same directory of `finance_tracker_bot.py` 
| `LOG_LEVEL` | a valid log level as documented by the `logging` module. Default is `INFO`
| `DB_USER` | username for Postgres (**required**). It should be possible to login to Postgres with `psql -U $DB_USER`
| `DB_PASS` | password of `DB_USER` (**required**)
| `DB_NAME` | database name where to store user data and APS jobs (**required**)
| `DATA_DIR` | where to store users' access tokens after a successful login with Google. Tokens are also stored in-memory (and saved to the database), so this should be considered as (less safe) backup location. Default is a `storage` directory

## Google API

Using Google Sheets API requires the authentication via OAuth2 and the user consent using a Google Account. The authentication token is retrieved by the bot during the auth step, but a credentials file (also known as "client secret" file) is required. The absolute path of this file should be stored in an environment variable named `CREDS_FILE`. If that variable is not set, the client secret filename is assumed to be `credentials.json` and placed in **the same directory of the bot**. The client secret file contains sensitive information, hence it should be kept in a safe location.

#### How to obtain a client secret file

The first prerequisite is to have an account on Google Cloud Platform and an active project (create a new one if necessary).

*[TODO]*

## Usage

Main commands:

- `/start`: start the bot
- `/record`: record a new expense/income, show or clear the current data stored locally
- `/summary`: obtain a summary from your spreadsheet data (**not implemented yet**)
- `/settings`: manage user's settings: login to Google, setup the spreadsheet, or configure the append task schedule
- `/help`: print a usage message

## Acknowledgments

- The versatile library [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- A Python wrapper to Google Sheets API: [gspread](https://github.com/burnash/gspread)