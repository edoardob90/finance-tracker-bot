import pytest
from currencies import currency_parser


def test_amount_string():
    amount = "1,000.00"
    assert currency_parser(amount) == (1000.00, None)


def test_amount_float():
    amount = -1000.00
    assert currency_parser(amount) == (-1000.00, None)


def test_empty_amount():
    amount = ""
    assert currency_parser(amount) == (0.00, None)


@pytest.mark.parametrize(
    "amount, expected",
    [
        ("-10e", (-10.00, "EUR")),
        ("99$", (99.00, "USD")),
        ("9usd", (9.0, "USD")),
        ("-666 c", (-666.00, "CHF")),
        ("1000 CHF", (1000.0, "CHF")),
        ("-1,000.01 €", (-1000.01, "EUR")),
        ("£1'009", (1009.0, "GBP")),
    ],
)
def test_amounts(amount, expected):
    assert currency_parser(amount) == expected
