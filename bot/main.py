import logging
import os
import pathlib as pl
import typing as t

from dotenv import load_dotenv
from finance_tracker_bot import FinanceTrackerBot


def main():
    # Load the .env file
    load_dotenv()

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=LOG_LEVEL
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Config
    bot_config: t.Dict[str, t.Any] = {
        "token": os.environ["TOKEN"],
        "data_dir": pl.Path(os.environ.get("DATA_DIR", "data")).expanduser().resolve(),
        "mode": os.environ.get("MODE", "polling"),
        "webhook_url": os.environ.get("WEBHOOK_URL", None),
        "port": int(os.environ.get("PORT", "5000")),
        "listen_url": os.environ.get("LISTEN_URL", "127.0.0.1"),
    }

    # Check that the token is provided
    if not bot_config["token"]:
        raise ValueError("A Telegram bot token (TOKEN) must be provided.")

    # Create the data directory if it doesn't exist
    bot_config["data_dir"].mkdir(parents=True, exist_ok=True)

    # ... other checks

    # Create and run the bot
    FinanceTrackerBot(bot_config).run()


if __name__ == "__main__":
    main()
