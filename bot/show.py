from models import Record
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


async def show_records(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


show_handler = CommandHandler("show", show_records)
