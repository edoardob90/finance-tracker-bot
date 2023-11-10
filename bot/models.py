import datetime as dt
import typing as t
from enum import Enum

from currencies import CURRENCIES_CODES, currency_parser
from dateutil.parser import parse as parse_date
from pydantic import BaseModel, field_validator, model_validator
from telegram import InlineKeyboardButton
from utils import escape_md


class MissingFieldsError(Exception):
    """An exception for missing required fields"""


class Amount(BaseModel):
    value: float | str
    currency: str | None = None

    @model_validator(mode="after")
    def validate_amount(self) -> "Amount":
        if isinstance(self.value, str) and self.currency is None:
            self.value, self.currency = currency_parser(self.value)
        return self

    @field_validator("currency")
    @classmethod
    def parse_currency(cls, v):
        if v not in CURRENCIES_CODES:
            raise ValueError(f"Unknown currency code: {v}")
        return v


class Record(BaseModel):
    """A class for a single record"""

    date: str | dt.date | None = None
    amount: Amount | None = None
    description: str | None = None
    account: str | None = None
    recorded_at: dt.datetime | None = None

    @field_validator("date")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            return parse_date(v, dayfirst=True).date()
        return v

    def __str__(self) -> str:
        _date = (
            self.date.strftime("%d/%m/%Y") if isinstance(self.date, dt.date) else None
        )

        _amount, _currency = (
            (self.amount.value, self.amount.currency) if self.amount else (None, None)
        )

        return "\n".join(
            [
                f"*Date:* {escape_md(_date)}",
                f"*Amount:* {escape_md(_amount)} {escape_md(_currency)}",
                f"*Description:* {escape_md(self.description)}",
                f"*Account:* {escape_md(self.account)}",
            ]
        ).replace("None", "")

    def check_required_fields(self) -> None:
        """Check if the required fields are present"""
        _missing_fields = set()

        if not self.date:
            _missing_fields.add("date")
        if not self.amount:
            _missing_fields.add("amount")
        if not self.account:
            _missing_fields.add("account")

        if _missing_fields:
            raise MissingFieldsError(
                "Missing required fields: {}".format(", ".join(_missing_fields))
            )


class CallbackData(Enum):
    """A base `Enum` class for callback data"""

    def as_button(self) -> InlineKeyboardButton:
        """Return a button for a callback data enum"""
        return InlineKeyboardButton(text=self.value, callback_data=self)

    @staticmethod
    def button(name: str) -> InlineKeyboardButton:
        """Return a button for a callback data enum"""
        _enum = getattr(CallbackData, name.upper())
        return InlineKeyboardButton(text=_enum.value, callback_data=_enum)

    @classmethod
    def buttons(cls) -> t.List[InlineKeyboardButton]:
        """Return a list of buttons for callback data enums"""
        return [member.as_button() for member in cls]
