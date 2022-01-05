# Finance Tracker bot

A Telegram bot that helps with your personal finances. It's an experimental and work-in-progress project that provides the following functions:

1. Record an expense/income in a local, persistent storage
2. Connect to a given Google Spreadsheet document via OAuth2

## Usage

Main commands:

- `/start`: start the bot and schedule a daily task to append the saved records to the spreadsheet. The task runs every day at 22:59 (UTC) and cannot be customized by the user (at the moment). The user can force the append action with the `/append_data` command (see below)
- `/record`: record a new expense/income
- `/auth`: start or check the authorization process to access Google Sheets
- `/summary`: obtain a summary from your spreadsheet data (*not implemented yet*)
- `/help`: print a usage message

*Hidden* commands:

- `/show_data`: print all the saved records not yet appended to the spreadsheet
- `/clear_data`: erase the saved records
- `/append_data`: immediately append saved records to the spreadsheet
- `/auth_data`: show the status of the authentication and the configured spreadsheet
- `/reset`: reset the spreadsheet, i.e., change ID and the sheet name where to append data

## Notes & to-do

- [ ] Persistent storage currently uses Python built-in `pickle` module as implemented by the `python-telegram-bot` library. Persistence classes of the library don't support user-defined classes, and for complex data or performance reasons it might be better to exploit some database (e.g., MySQL, MongoDB, Redis)
- [ ] The periodic task to append data to the spreadsheet is to avoid too many calls to Google APIs. Since appending data is a blocking operation, using a scheduled task also mitigates slow connections. It would be ideal to implement this task in a fully async fashion

## Acknowledgments

- The versatile library [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- A Python wrapper to Google Sheets API: [gspread](https://github.com/burnash/gspread)