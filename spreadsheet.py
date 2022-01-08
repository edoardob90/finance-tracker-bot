from typing import List, NoReturn, Any

from gspread import Client, Worksheet
from gspread.exceptions import APIError

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

class SpreadsheetError(Exception):
    """A subclass for exceptions raised by the Spreadsheet class"""

class Spreadsheet():
    """A class for a Google Spreasheet object"""
    def __init__(self, client, spreadsheet_id=None, sheet_name=None):
        # A valid gspread Client
        self._client: Client = client
        # Properties
        self._spreadsheet_id: str = spreadsheet_id # the spreadsheet ID
        self._sheet_name: str = sheet_name # the sheet name
        self._range: str = None # the table range
        self._sheet: Worksheet = None
        self._records: List = None

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
    def sheet(self) -> Worksheet:
        try:
            doc = self._client.open_by_key(self.spreadsheet_id)
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
    def append_records(self, values: List[List]) -> Any:
        """Append one or more records to the spreadhseet"""
        return self.sheet.append_rows(values, value_input_option="USER_ENTERED", table_range=self.range)