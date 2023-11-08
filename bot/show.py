import typing as t

from models import Record, RecordSchema
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


async def show_records(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the saved records"""

    if _records := context.user_data["records"]:
        records = t.cast(t.List[Record], RecordSchema().load(_records, many=True))

        reply_text = "\n\n".join(
            [f"__RECORD \#{i}__\n{record}" for i, record in enumerate(records, start=1)]
        )
    else:
        reply_text = "⚠️ No records found\."

    await update.message.reply_text(reply_text)


show_handler = CommandHandler("show", show_records)
