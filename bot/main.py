import logging
import os
import pathlib as pl
import typing as t

import tomllib as toml
from finance_tracker_bot import FinanceTrackerBot
from openai_api import OpenAI


def main():
    # Load the .config file
    config_filepath = pl.Path.cwd() / ".config.toml"
    try:
        with config_filepath.open(mode="rb") as config_file:
            config: t.Dict[str, t.Any] = toml.load(config_file)
    except FileNotFoundError as err:
        raise RuntimeError("The .config.toml file is missing.") from err

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", config.get("log_level", "INFO"))
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=LOG_LEVEL
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Check that the token is provided
    if not config["bot"]["token"]:
        raise ValueError("A Telegram bot token (TOKEN) must be provided.")

    # Create the data directory
    data_dir = pl.Path(config["bot"].get("data_dir") or "./data").expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    config["bot"]["data_dir"] = data_dir

    # Setup the OpenAI API
    openai_api = OpenAI(config["openai"])

    # Create and run the bot
    bot = FinanceTrackerBot(config["bot"], openai_api)
    bot.run()


if __name__ == "__main__":
    main()
