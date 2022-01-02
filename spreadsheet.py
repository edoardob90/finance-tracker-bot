import os
from typing import List, NoReturn

import gspread
from gspread.exceptions import APIError

# DOCUMENT_ID = os.environ.get('GOOGLE_SHEET_ID')
# RANGE = os.environ.get('RANGE')
# SHEET_NAME = os.environ.get('SHEET_NAME')
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

class SpreadsheetError(Exception):
    """A subclass for exceptions raised by the Spreadsheet class"""

class Spreadsheet():
    """A class for a Google Spreasheet object"""
    def __init__(self, client):
        # A valid gspread Client
        self.client = client
        # Properties
        self._spreadsheet_id = None
        self._sheet_name = None
        self._range = None
        self._sheet = None
        self._records = None

    # Properties with accessors
    @property
    def spreadsheet_id(self) -> str:
        """The spreadsheet ID"""
        return self._spreadsheet_id
    
    @spreadsheet_id.setter
    def spreadsheet_id(self, id_: str) -> NoReturn:
        self._spreadsheet_id = id_

    @property
    def sheet_name(self) -> str:
        return self._sheet_name

    @sheet_name.setter
    def sheet_name(self, name: str) -> NoReturn:
        self._sheet_name = name

    @property
    def sheet(self) -> gspread.spreadsheet.Spreadsheet:
        try:
            doc = self.client.open_by_key(self.spreadsheet_id)
            sheet = doc.worksheet(self.sheet_name)
        except APIError:
            raise SpreadsheetError("Spreadsheet ID {} was not found.".format(self.spreadsheet_id))
        
        self._sheet = sheet
        
        return self._sheet

    @sheet.setter
    def sheet(self) -> NoReturn:
        raise SpreadsheetError("Cannot set the spreadsheet object.")

    @property
    def range(self) -> str:
        return self._range
    
    @range.setter
    def range(self, range: str) -> NoReturn:
        self._range = range

    # Methods
    def append_record(self, values: List):
        return self.sheet.append_row(values, value_input_option="USER_ENTERED", table_range=self.range)

# def get_sheet(self):
#     """The spreadsheet object retreived by ID"""
#     try:
#         doc = self.client.open_by_key(self.sheet_id) # instance of `gspread.models.Spreadsheet`
#         self._sheet = doc.worksheet(self._sheet_name) # instance of `gspread.models.Worksheet`
#         return self._sheet
#     except APIError:
#         raise SpreadsheetError("Spreadsheet with ID {} was not found.".format(self.sheet_id))

# def get_records(self):
#     """Get all the records of the spreadsheet"""
#     self.records = self.get_sheet().get_all_records()
#     return self.records

# def append_record(self, values):
#     """Append a record to the spreadsheet"""
#     return self.get_sheet().append_row(values, value_input_option="USER_ENTERED", table_range=self.range)

# def remove_record(self):
#     """Remove a record from the spreadsheet"""
#     pass

# def update_record(self):
#     """Edit a record of the spreadsheet"""
#     pass