# Finance Tracker bot

A Telegram bot that helps with your personal finances. It's an experimental and work-in-progress project that provides (or will provide in the future) the following functions:

1. Record an expense/income in a local, persistent storage
2. Connect to a given Google Spreadsheet document via OAuth2 (or a service account)
3. Query the data stored in the Google Spreadsheet, e.g., to report monthly summaries or to set alerts on some expense categories

## Setup

### Bot config

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
| `SERVICE_ACCOUNT` | if `True`, instructs the bot to use a service account instead of the default OAuth credentials (see below). Default is `False` |
| `SERVICE_ACCOUNT_FILE` | path to the service account credentials JSON file. This file is read only if `SERVICE_ACCOUNT=True` |
| `LOG_LEVEL` | a valid log level as documented by the `logging` module. Default is `INFO`
| `DB_USER` | username for Postgres (**required**). It should be possible to login to Postgres with `psql -U $DB_USER`
| `DB_PASS` | password of `DB_USER` (**required**)
| `DB_NAME` | database name where to store user data and APS jobs (**required**)
| `DATA_DIR` | where to store users' access tokens after a successful login with Google. Tokens are also stored in-memory (and saved to the database), so this should be considered as (less safe) backup location. Default is a `storage` directory

### Google API

Using Google Sheets API requires the authentication via OAuth2 and the user consent using a Google Account. The authentication token is retrieved by the bot during the auth step, but a credentials file (also known as "client secret" file) is required. The absolute path of this file should be stored in an environment variable named `CREDS_FILE`. If that variable is not set, the client secret filename is assumed to be `credentials.json` and placed in **the same directory of the bot**. The client secret file contains sensitive information, hence it should be kept in a safe location.

The prerequisite is to have an account on [Google Cloud Platform](https://console.developers.google.com/) and an active project (create a new one if necessary) that will represent the bot activity on Google Cloud.

#### Enable API access

To enable an API for your project:

1. Open the [API Library](https://console.developers.google.com/apis/library) in the Google API Console.
3. Search for and enable the following APIs:
    - Google Drive API
    - Google Sheets API
5. If prompted, enable billing.
6. If prompted, read and accept the API's Terms of Service.


#### Using OAuth credentials `#TODO`

Steps:

- Create authorization credentials
- Select appropriate scopes
- Download the client secret file

#### Using a service account

From [Google Cloud docs](https://cloud.google.com/iam/docs/understanding-service-accounts#background):

> A service account is a special type of Google account intended to represent a non-human user that needs to authenticate and be authorized to access data in Google APIs.

A service account is a separate Google account, therefore it **doesn't have** any spreadsheets until you share one with it. This is a key difference between a user account and a service account: except when setting up [domain-wide delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority), a service account **is not meant** to access user's data but only its own data. Therefore, the best way to authorize the bot to access a user's data on Google Sheet is to use OAUth 2.0 credentials.

To authorize the service account you **must** share the Google spreadsheet with it and set its role to **Editor**. Otherwise, the bot will raise an error indicating that either:

- a spreadsheet with a given ID cannot be found → you forgot to share the spreadsheet;
- it doesn't have the permissions to edit the spreadsheet → you set the wrong role.

First, create a service account:

1. Open the [Service accounts page](https://console.developers.google.com/iam-admin/serviceaccounts).
1. Select a project you created for the bot.
1. Click add **Create service account**.
1. Under Service account details, type a name, ID, and description for the service account, then click Create and continue.
1. *Optional*: Under Grant this service account access to project, select the IAM roles to grant to the service account.
1. Click Continue.
1. *Optional*: Under Grant users access to this service account, add the users or groups that are allowed to use and manage the service account.
1. Click Done.
1. Click add Create key, then click Create.

Next, create a service account key:

1. Click the email address for the service account you created.
1. Click the Keys tab.
1. In the Add key drop-down list, select Create new key.
1. Click Create.

A new private/public key-pair is generated and downloaded to your machine. This JSON file contains the **only copy of the service account private key**, hence it must be stored safely. Place it in a location that the bot can access and note down its path: this path will be the value of `SERVICE_ACCOUNT_FILE` field in the bot config file (see table above).

The instructions above are the bare minimum to make the bot interact with Google Sheets via a service account and are far from exhaustive. To know more, check out the official Google [documentation on IAM roles and service accounts](https://cloud.google.com/iam/docs/service-accounts).

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
