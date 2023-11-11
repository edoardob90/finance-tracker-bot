import datetime as dt
import logging
import typing as t

import openai
from openai.types.audio import Transcription
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.completion_create_params import Function

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
FUNCTIONS: t.List[Function] = [
    Function(
        name="parse_expense_income_record",
        description=(
            "Parse an input string with the details of an expense or income record. "
            "Return a dictionary representing the record. "
            "Translate in English if necessary."
        ),
        parameters=dict(
            type="object",
            properties=dict(
                date=dict(
                    type="string",
                    description="The record date, in ISO8601 format",
                ),
                amount=dict(
                    type="object",
                    description=(
                        "The amount of the expense or income, represented as a dict. "
                        "An expense must have a negative value, while an income a positive one. "
                        "The currency must be expressed with its currency code, e.g., EUR, USD, GBP, etc."
                    ),
                    properties=dict(
                        value=dict(type="number"),
                        currency=dict(type="string"),
                    ),
                ),
                description=dict(
                    type="string",
                    description="A short summary about the expense or income",
                ),
                account=dict(
                    type="string",
                    description="The account where the transaction happened",
                ),
            ),
            required=["date", "amount", "currency", "account"],
        ),
    ),
]


class OpenAI:
    """OpenAI API wrapper"""

    def __init__(self, config: t.Dict[str, t.Any]) -> None:
        """Initialize the OpenAI API wrapper"""

        # OpenAI API config
        self.api_key: str | None = config.get("api_key")

        # Set chosen model or use the default one
        self.model: str = config.get("model", "gpt-3-5-turbo")

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
        messages = [
            ChatCompletionSystemMessageParam(
                role="system",
                content=f"Today is {dt.date.today().strftime('%A, %d %B %Y')}.",
            ),
            ChatCompletionUserMessageParam(role="user", content=query),
        ]

        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                functions=FUNCTIONS,
            )
        except openai.OpenAIError as err:
            logging.error("Error while calling the OpenAI API: %s", err)
            raise err

        return response
