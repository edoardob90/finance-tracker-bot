from typing import Dict, List, NoReturn, Any, Union

from gspread import Client, Worksheet
from gspread import Spreadsheet as Document
from gspread.exceptions import APIError, WorksheetNotFound

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
        self._doc: Document = None
        self._sheet: Worksheet = None
        self._range: str = None # the table range

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
    def doc(self) -> Document:
        if not self.spreadsheet_id:
            raise SpreadsheetError('Spreadsheet ID is undefined!')

        try:
            doc = self._client.open_by_key(self.spreadsheet_id)
        except APIError:
            raise SpreadsheetError("A spreadsheet with ID '{}' was not found.".format(self.spreadsheet_id))

        self._doc = doc

        return self._doc
    
    @doc.setter
    def doc(self, id_: str = None) -> NoReturn:
        raise SpreadsheetError('Spreadsheet document should only be set by providing the spreadsheet ID.')

    @property
    def sheet(self) -> Worksheet:
        try:
            sheet = self.doc.worksheet(self.sheet_name)
        except (APIError, WorksheetNotFound):
            raise SpreadsheetError("A sheet with name '{}' does not exist!".format(self.sheet_name))
        
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

    def get_records(self, sheet_name: str = None, range_: str = None, as_dict: bool = False, **kwargs) -> List | List[Dict]:
        """Get records from a range (A1 notation) or an entire sheet"""
        # If `sheet` is not given, check if it's already been set
        if sheet_name:
            self.sheet_name = sheet_name
        
        if self.sheet_name is None:
            all_sheets_names = [str(sheet.title) for sheet in self.doc.worksheets()]
            raise SpreadsheetError(f"Cannot get data from an unnamed sheet! Available sheets: '{', '.join(all_sheets_names)}'")
        
        # Set the range if given
        if range_:
            self.range = range_
        
        if self.range:
            values = self.sheet.get_values(self.range)
        else:
            values = self.sheet.get_all_records(**kwargs) if as_dict else self.sheet.get_all_values()
    
        return values