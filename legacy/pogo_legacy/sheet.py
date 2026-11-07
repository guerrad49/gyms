"""
PokemonGo.sheet
----------------------

This module contains the GymSheet class which extends the 
`gspread` package for PokemonGo data. In particular, the 
GymSheet class aims to automate the process of writing 
new information to a Google sheet.

See Also
--------
gspread
README - instructions on how to generate json key
"""


from typing import Optional

import numpy as np
import pandas as pd
from gspread import service_account

from .exceptions import TitleNotFound, InputError
from .utils import are_similar


class GymSheet:
    """
    An instance of this class handles access to a Google Sheets' 
    spreadsheet containing a database of gyms.
    
    :param str keyPath: The path to json key required for API access.
    :param str sheetName: The spreadsheet name.
    :param bool verbose: (optional) If True, print progress statements.

    Examples:

    .. code:: python

        >>> # instance w/ required parameters
        >>> myKey = 'path/to/json/key'
        >>> gs = GymSheet(myKey, 'my_sheet_name')

    .. note::
        Read/write access to a spreadsheet is handled using 
        `gspread <https://docs.gspread.org/en/latest/index.html>`__.
        The :attr:`GymSheet.sheet` attribute stores a spreadsheet of type 
        :class:`gspread.worksheet.Worksheet`. We always assume the database 
        is contained in "Sheet1" of a spreadsheet.
    """
    
    def __init__(
            self, 
            keyPath: str, 
            sheetName: str, 
            verbose: Optional[bool] = False
            ) -> None:

        self.verbose = verbose
        self._retrieve_data(keyPath, sheetName)
        self.errors = list()


    def _retrieve_data(
            self, 
            keyPath: str, 
            sheetName: str
            ) -> None:
        """
        Partition sheet records into dataframes. This method is/should only 
        be called at instantiation to access database.
        """

        client     = service_account(keyPath)
        self.sheet = client.open(sheetName).sheet1
        records    = self.sheet.get_all_records()
        df         = pd.DataFrame(records)
        df.index   = np.arange(2, len(df) + 2)    # Start at row 2.

        self.processed   = df[df['uid'] != '']
        self.unprocessed = df[df['uid'] == '']

        if self.verbose:
            print('INFO - Google sheet data extracted successfully.')
    
    
    def find_title(
            self, 
            inTitle: str, 
            isUpdate: Optional[bool] = False
            ) -> tuple[str, int]:
        """
        Find a gym title in the spreadsheet. If no exact match, look for 
        similar matches (see :meth:`utils.are_similar`). If no match still, 
        the output will contain an empty title.
        
        :param str inTitle: The title to locate.
        :param bool isUpdate: (optional) If True, specifies update to 
            `inTitle` data.
        :returns: The title and row index values in the database.
        """

        if not isUpdate:
            df = self.unprocessed
        else:
            df = self.processed
        
        matches = df[df['title'] == inTitle]
        self.errors.clear()

        # Check similar titles when no exact match.
        if matches.shape[0] == 0:
            matches = df[df['title']
                    .apply(lambda x: are_similar(x, inTitle))
                    ]
        
        # Default values to return.
        outTitle = ''
        rowIndex = -1

        # Only one match.
        if matches.shape[0] == 1:
            outTitle = matches.iat[0,1]
            rowIndex = matches.index[0]
        #  Multiple matches.
        elif matches.shape[0] > 1:
            outTitle, rowIndex = self._find_from_dupes(matches)
        # No matches.
        else:
            self.errors.append('TITLE')
        
        return outTitle, rowIndex


    def prompt_for_title(
            self, 
            isUpdate: Optional[bool] = False
            ) -> tuple[str, int]:
        """
        Find a gym title in the spreadsheet by prompting the user to 
        provide the title. Adds an extra layer to :meth:`find_title`.
        
        :param bool isUpdate: (optional) If True, specifies update to 
            `inTitle` data.
        :returns: The title and row index values in the database.
        :raises TitleNotFound: if title search unsuccessful.
        """
        
        prompt = 'Enter correct TITLE for badge:\n\t'
        title = input(prompt).strip()

        outTitle, rowIndex = self.find_title(title, isUpdate=isUpdate)
        if rowIndex == -1:
            raise TitleNotFound

        return outTitle, rowIndex
    

    def _find_from_dupes(
            self, 
            duplicates: pd.core.frame.DataFrame
            ) -> tuple[str, int]:
        """
        Find a gym title and row index from a list of duplicates 
        (or near duplicates).

        .. versionadded:: 1.1.0
        """
        
        outTitle = duplicates.iat[0,1]
        columns  = ['title','latlon','city','state']
        prompt   = 'Duplicates found.\n'
        prompt  += duplicates[columns].to_string()
        prompt  += '\nEnter correct INDEX:\t'
        rowIndex = int(input(prompt))

        if rowIndex not in duplicates.index:
            raise InputError
        
        return outTitle, rowIndex


    def write_to_row(
            self, 
            rowIndex: int, 
            rowData: dict
            ) -> None:
        """
        Write data to spreadsheet row. The `rowData` should contain all 
        the fields from a row in order.
        
        :param int rowIndex: The spreadsheet's row index.
        :param dict rowData: The row data.
        """

        # Get gym values needed.
        rowValues = list(rowData.values())

        # rowValues -> A:N is one-to-one mapping.
        oldRow = 'A{0}:N{0}'.format(rowIndex)
        self.sheet.update(oldRow, [rowValues])
        
        if self.verbose:
            print('Writing to row {}'.format(rowIndex))
            print(rowValues)


    def geo_sort(self) -> None:
        """
        Sort the spreadsheet contents geographically.
        """
        
        cols = self.sheet.row_values(1)   # Column titles.

        # (column index, 'ascending')
        byCity   = (cols.index('city')   + 1, 'asc')
        byCounty = (cols.index('county') + 1, 'asc')
        byState  = (cols.index('state')  + 1, 'asc') 
        byTitle  = (cols.index('title')  + 1, 'asc')
        
        rowLen = 'A2:N{}'.format(self.sheet.row_count)

        # Sort by state, then county, then city.
        self.sheet.sort(
            byState, byCounty, byCity, byTitle, 
            range=rowLen
            )
        
        if self.verbose:
            print('INFO - Sorting complete.\n')
