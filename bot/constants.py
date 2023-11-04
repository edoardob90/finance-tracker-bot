# pylint: disable=invalid-name,line-too-long,anomalous-backslash-in-string
"""
Constants
"""

# Record's fields
RECORD_KEYS = ("date", "reason", "amount", "currency", "account", "recorded_on")

# Currencies supported
CURRENCIES = dict(
    (
        ("E", "EUR"),
        ("€", "EUR"),
        ("U", "USD"),
        ("$", "USD"),
        ("C", "CHF"),
        ("G", "GBP"),
        ("£", "GBP"),
    )
)

# Spreadsheet scopes
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
