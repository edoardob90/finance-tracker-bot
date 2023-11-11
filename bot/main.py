import logging
import os
import pathlib as pl
import typing as t

from dotenv import load_dotenv
from finance_tracker_bot import FinanceTrackerBot
from openai_api import OpenAI


def main():
    # Load the .env file
    load_dotenv()

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=LOG_LEVEL
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Bot config
    bot_config: t.Dict[str, t.Any] = {
        "token": os.environ.get("TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("BOT_TOKEN"),
        "bot_language": os.environ.get("BOT_LANGUAGE", "en"),
        "data_dir": pl.Path(os.environ.get("DATA_DIR", "data")).expanduser().resolve(),
        "mode": os.environ.get("MODE", "polling"),
        "webhook_url": os.environ.get("WEBHOOK_URL", None),
        "port": int(os.environ.get("PORT", "5000")),
        "listen_url": os.environ.get("LISTEN_URL", "127.0.0.1"),
        "openai_allowed_users": os.environ.get("OPENAI_ALLOWED_USERS", "").split(","),
    }

    # OpenAI API config
    openai_config: t.Dict[str, t.Any] = {
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "model": os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
    }

    # Check that the token is provided
    if not bot_config["token"]:
        raise ValueError("A Telegram bot token (TOKEN) must be provided.")

    # Create the data directory if it doesn't exist
    bot_config["data_dir"].mkdir(parents=True, exist_ok=True)

    # ... other checks

    # Setup the OpenAI API
    openai_api = OpenAI(openai_config)

    # Create and run the bot
    FinanceTrackerBot(bot_config, openai_api).run()


if __name__ == "__main__":
    main()
