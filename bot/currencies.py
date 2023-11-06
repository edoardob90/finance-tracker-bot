import typing as t

CURRENCIES: t.Dict[str, t.Dict] = {
    "EUR": {"symbol": "€", "name": "Euro", "aliases": ("E", "e", "€", "eur", "euro")},
    "USD": {"symbol": "$", "name": "US Dollar", "aliases": ("U", "$", "usd", "dollar")},
    "CHF": {
        "symbol": "CHF",
        "name": "Swiss Franc",
        "aliases": ("C", "c", "chf", "franc", "Sfr."),
    },
    "GBP": {
        "symbol": "£",
        "name": "British Pound",
        "aliases": ("G", "£", "gbp", "pound"),
    },
}

CURRENCIES_CODES: t.List[str] = list(CURRENCIES.keys())
CURRENCIES_SYMBOLS: t.List[str] = [c["symbol"] for c in CURRENCIES.values()]


def symbol_from_str(alias: str | None) -> str:
    """Return the symbol of a currency from its alias"""
    for currency, props in CURRENCIES.items():
        if alias in props["aliases"]:
            return currency

    return ""
