import typing as t

from telegram.ext import BaseHandler

if t.TYPE_CHECKING:
    from finance_tracker_bot import FinanceTrackerBot


class HandlerBase:
    """A base class for all the handlers"""

    def __init__(self, bot: "FinanceTrackerBot") -> None:
        self.bot = bot
        self._handlers: t.List[BaseHandler] | None = None
        self._command: str | None = None

    @property
    def handlers(self) -> t.List[BaseHandler]:
        """Return the handler"""
        if not self._handlers:
            raise ValueError(f"Handler {self.__class__.__name__} not initialized.")
        return self._handlers
