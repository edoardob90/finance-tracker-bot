"""
Constants
"""
import os
from os.path import join, dirname, exists

# Logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_level = os.environ.get('LOG_LEVEL', 'INFO')

# The three conversation states:
# CHOOSING = 0
# CHOICE = 1
# REPLY = 2
CHOOSING, CHOICE, REPLY = range(3)

# Path to Google API client secret file
CREDS = os.environ.get("CREDS_FILE", join(dirname(__file__), "credentials.json"))
DATA_DIR = os.environ.get("DATA_DIR", join(dirname(__file__), "storage"))

# Create DATA_DIR if it doesn't exist
if not exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# Currencies supported
CURRENCIES = dict((
    ('E', 'EUR'),
    ('U', 'USD'),
    ('C', 'CHF')
))