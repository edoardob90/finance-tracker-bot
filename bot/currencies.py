import re
import typing as t
from itertools import chain


class CurrencyParsingError(Exception):
    """An exception for currency parsing errors"""


CURRENCIES: t.Dict[str, t.Dict[str, t.Any]] = {
    "EUR": {"symbol": "€", "name": "Euro", "aliases": ("€", "eur", "euro")},
    "USD": {
        "symbol": "$",
        "name": "US Dollar",
        "aliases": ("us$", "usd", "dollar"),
    },
    "CHF": {
        "symbol": "CHF",
        "name": "Swiss Franc",
        "aliases": ("chf", "franc", "Sfr.", "sfr.", "Sfr", "sfr"),
    },
    "GBP": {
        "symbol": "£",
        "name": "British Pound",
        "aliases": ("gbp", "pound", "UKP", "ukp", "quid", "sterling"),
    },
}

CURRENCIES_CODES: t.List[str] = list(CURRENCIES.keys())
CURRENCIES_SYMBOLS: t.List[str] = [c["symbol"] for c in CURRENCIES.values()]
CURRENCIES_ALIASES: t.Set[str] = set(
    chain.from_iterable(c["aliases"] for c in CURRENCIES.values())
)


def or_regex(symbols: t.List[str] | t.Set[str]) -> re.Pattern:
    """Return a regex pattern that matches any of the given symbols"""
    return re.compile(r"|".join(re.escape(s) for s in symbols))


def extract_currency(amount: str) -> str | None:
    """Extract the currency symbol from an amount string"""
    if not amount:
        return None

    _search_methods = [
        or_regex(CURRENCIES_CODES).search,
        or_regex(CURRENCIES_SYMBOLS).search,
        or_regex(CURRENCIES_ALIASES).search,
    ]

    for method in _search_methods:
        if (match := method(amount)) is not None:
            return match.group(0)

    return None


def extract_number(amount: str) -> str | None:
    """
    Extract the number part from an amount string
    Adapted from https://github.com/scrapinghub/price-parser
    """
    amount = re.sub(
        r"\s+", " ", amount
    )  # clean initial text from non-breaking and extra spaces

    if amount.count("€") == 1:
        m = re.search(
            r"""
        [\d\s.,]*?\d    # number, probably with thousand separators
        \s*?€(\s*?)?    # euro, probably separated by whitespace
        \d(?(1)\d|\d*?) # if separated by whitespace - search one digit, multiple digits otherwise
        (?:$|[^\d])     # something which is not a digit
        """,
            amount,
            re.VERBOSE,
        )

        if m:
            return m.group(0).replace(" ", "")

    m = re.search(
        r"""
        ([-]?[.]?\d[\d\s.,']*)   # number, probably with thousand separators
        \s*?                    # skip whitespace
        (?:[^%\d]|$)            # capture next symbol - it shouldn't be %
        """,
        amount,
        re.VERBOSE,
    )

    if m:
        price_text = m.group(1).rstrip(",.")
        return (
            price_text.strip()
            if price_text.count(".") == 1
            else price_text.lstrip(",.").strip()
        )

    if "free" in amount.lower():
        return "0"

    return None


def parse_number(number: str | None) -> float | None:
    if not number:
        return None

    number = number.strip().replace(" ", "").replace("'", "")

    _search_decimal_sep = re.compile(
        r"""
            \d*        # null or more digits (there can be more before it)
            ([.,€])    # decimal separator
            (?:        # 1,2 or 4+ digits. 3 digits is likely to be a thousand separator
            \d{1,2}?|
            \d{4}\d*?
            )
            $
        """,
        re.VERBOSE,
    )

    decimal_separator = None

    if match := _search_decimal_sep.search(number):
        decimal_separator = match.group(1)

    if decimal_separator is None:
        number = number.replace(".", "").replace(",", "")
    elif decimal_separator == ".":
        number = number.replace(",", "")
    elif decimal_separator == ",":
        number = number.replace(".", "").replace(",", ".")
    else:
        assert decimal_separator == "€"
        number = number.replace(".", "").replace(",", "").replace("€", ".")

    try:
        return float(number)
    except ValueError:
        return None


def currency_parser(amount: str | t.Any) -> t.Tuple[float, str | None]:
    """Parse a number string that contains a currency symbol or name"""
    _amount = str(amount)

    # Extract the currency part
    currency = extract_currency(_amount)

    # Extract the number part
    number = extract_number(_amount)

    # Parse the number
    number_value = parse_number(number)

    print(symbol_from_str(currency), number_value)

    return round(number_value, 2) if number_value else 0.0, symbol_from_str(currency)


def symbol_from_str(alias: str | None) -> str | None:
    """Return the symbol of a currency from its alias"""
    if not alias:
        return

    for currency, props in CURRENCIES.items():
        if alias in {currency, props["symbol"]} | set(props["aliases"]):
            return currency
