import datetime as dt
import typing as t
from enum import Enum

from currencies import CURRENCIES_CODES, currency_parser
from dateutil.parser import parse as parse_date
from marshmallow import Schema, fields, post_load
from telegram import InlineKeyboardButton
from utils import escape_md


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


class Record:
    """A class for a single record"""

    def __init__(
        self,
        date: dt.date | None = None,
        amount: float | None = None,
        currency: str | None = None,
        description: str | None = None,
        account: str | None = None,
        recorded_at: dt.datetime | None = None,
    ) -> None:
        self._date = date
        self._amount = amount
        self._currency = currency
        self._description = description
        self._account = account
        self._recorded_at = recorded_at

    @property
    def date(self) -> dt.date | None:
        return self._date

    @date.setter
    def date(self, value: str) -> None:
        self._date = parse_date(value, dayfirst=True).date()

    @property
    def amount(self) -> float | None:
        return self._amount

    @amount.setter
    def amount(self, value: str) -> None:
        self._amount, self._currency = currency_parser(value)

    @property
    def currency(self) -> str | None:
        return self._currency

    @currency.setter
    def currency(self, value: str) -> None:
        if value not in CURRENCIES_CODES:
            raise ValueError(f"Unknown currency code: {value}")
        self._currency = value

    @property
    def description(self) -> str | None:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    @property
    def account(self) -> str | None:
        return self._account

    @account.setter
    def account(self, value: str) -> None:
        self._account = value

    @property
    def recorded_at(self) -> dt.datetime | None:
        return self._recorded_at

    @recorded_at.setter
    def recorded_at(self, value: dt.datetime) -> None:
        self._recorded_at = value

    def __str__(self) -> str:
        return "\n".join(
            [
                f"*Date:* {escape_md(self.date.strftime('%d/%m/%Y'))}",
                f"*Amount:* {escape_md(self.amount)} {escape_md(self.currency)}",
                f"*Description:* {escape_md(self.description)}",
                f"*Account:* {escape_md(self.account)}",
            ]
        ).replace("None", "")

    def validate(self) -> None:
        """Validate the record"""
        _missing_fields = set()

        if not self.date:
            _missing_fields.add("date")
        if not self.amount:
            _missing_fields.add("amount")
        if not self.account:
            _missing_fields.add("account")

        if _missing_fields:
            raise ValueError(
                "Missing required fields: {}".format(", ".join(_missing_fields))
            )


class RecordSchema(Schema):
    """A schema for a single record""" ""

    date = fields.Date(allow_none=True)
    amount = fields.Float(allow_none=True)
    currency = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    account = fields.Str(allow_none=True)
    recorded_at = fields.DateTime(allow_none=True)

    @post_load
    def make_record(self, data: dict, **kwargs: dict) -> Record:
        return Record(**data)
