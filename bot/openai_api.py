import datetime as dt
import io
import logging
import pathlib as pl
import typing as t

import openai
from openai.types.audio import Transcription
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

# OpenAI models
GPT_STABLE_MODELS = ("gpt-3-5-turbo", "gpt-4")
GPT_3_MODELS = (
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-16k-0613",
)
GPT4_MODELS = ("gpt-4-32k", "gpt-4-1106-preview", "gpt-4-0613", "gpt-4-32k-0613")
GPT_ALL_MODELS = GPT_STABLE_MODELS + GPT_3_MODELS + GPT4_MODELS


# OpenAI functions specs
FUNCTIONS: t.List[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "parse_expense_income_record",
            "description": "Parse an input string with the details of an expense record and return a dict representing the record. Translate in English if necessary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The record date, in ISO8601 format",
                    },
                    "amount": {
                        "type": "object",
                        "description": (
                            "The amount of the expense or income, represented as a dict. "
                            "An expense must have a negative value, while an income a positive value. "
                            "The currency must be expressed with its currency code, e.g., EUR, USD, GBP, etc."
                        ),
                        "properties": {
                            "value": {"type": "number"},
                            "currency": {"type": "string"},
                        },
                    },
                    "description": {
                        "type": "string",
                        "description": "A short summary about the expense or income",
                    },
                    "account": {
                        "type": "string",
                        "description": "The account where the transaction happened",
                    },
                },
                "required": ["date", "amount", "currency", "account"],
            },
        },
    }
]


class OpenAI:
    """OpenAI API wrapper"""

    def __init__(self, config: t.Dict[str, t.Any]) -> None:
        """Initialize the OpenAI API wrapper"""
        # Bot language
        self.language: str = config.get("language", "en")

        # OpenAI API key
        self.api_key: str | None = config.get("api_key")

        # Set chosen model or use the default one
        self.model: str = config.get("model", "gpt-3-5-turbo")
        self.whisper_model = "whisper-1"

        # Check that the API key is provided
        if not self.api_key:
            raise ValueError("An OpenAI API key (OPENAI_API_KEY) must be provided.")

        # Set the API key
        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    def change_model(self, model: str) -> None:
        """Change the model"""
        if model not in GPT_ALL_MODELS:
            raise ValueError(f"Unknown model: {model}")

        self.model = model

    async def get_chat_response(self, query: str) -> ChatCompletion:
        """Get a chat response"""
        messages: t.List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are an helpful assistant. "
                "Your task is to read a natural language input that describes expenses or income and extract meaningful details from them",
            },
            {
                "role": "user",
                "content": "Today is {}.".format(
                    dt.date.today().strftime("%A, %d %B %Y")
                ),
            },
            {"role": "user", "content": "New record input: {}".format(query)},
        ]

        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                messages=messages, model=self.model, tools=FUNCTIONS, tool_choice="auto"
            )
        except openai.OpenAIError as err:
            logging.error("Error while calling the OpenAI API: %s", err)
            raise err

        return response

    async def get_transcription(
        self, audio_file: t.IO[bytes] | pl.Path
    ) -> Transcription:
        """Transcribe an audio file"""
        if isinstance(audio_file, pl.Path):
            audio_file = io.BytesIO(audio_file.read_bytes())
        try:
            response = await self.client.audio.transcriptions.create(
                file=audio_file, model=self.whisper_model, language=self.language
            )
        except FileNotFoundError:
            logging.error(f"File '{audio_file.name}' cannot be found")
            raise
        except Exception:
            logging.error("Error while performing an audio transcription API request")
            raise

        return response
