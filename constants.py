"""
Constants
"""
import os
from os.path import join, dirname
import logging

# Logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_level = logging.DEBUG

# The three conversation states:
# CHOOSING = 0
# CHOICE = 1
# REPLY = 2
CHOOSING, CHOICE, REPLY = range(3)

# Path to Google API client secret file
CREDS = os.environ.get("CREDS_FILE", join(dirname(__file__), "credentials.json"))

# Currencies supported
CURRENCIES = dict((
    ('E', 'EUR'),
    ('U', 'USD'),
    ('C', 'CHF')
))