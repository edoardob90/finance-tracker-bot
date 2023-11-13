import logging
import typing as t

from models import Record
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, PrefixHandler

if t.TYPE_CHECKING:
    from finance_tracker_bot import FinanceTrackerBot

from handlers import HandlerBase

logger = logging.getLogger(__name__)


class ShowHandler(HandlerBase):
    """A class for the /show command"""

    def __init__(self, bot: "FinanceTrackerBot") -> None:
        super().__init__(bot)
        self._command = "show"
        self._handlers = [
            PrefixHandler("?", self._command, self.print_help),
            CommandHandler(self._command, self.show_records),
        ]

    async def print_help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Print the help message"""
        help_message = "🆘 *HELP ABOUT THE* `/show` *COMMAND*\n\n"

        await update.message.reply_text(help_message)

    async def show_records(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show the saved records"""

        if _records := context.user_data["records"]:
            records = [Record.model_validate(r) for r in _records]

            reply_text = (
                f"You saved *{len(records)}* record{'s' if len(records) > 1 else ''}:\n\n"
                + "\n\n".join(
                    [
                        (
                            f"*__Record \#{i}__* "
                            f"\({record.recorded_at.strftime('%d/%m/%Y, %H:%M')}\)\n\n"
                            f"{record}"
                        )
                        for i, record in enumerate(records, start=1)
                    ]
                )
            )
        else:
            reply_text = "⚠️ No records found\."

        await update.message.reply_text(reply_text)
