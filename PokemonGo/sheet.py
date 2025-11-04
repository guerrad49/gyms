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

from .exceptions import TitleNotFound
from .utils import are_similar


class GymSheet:
    """
    An instance of this class handles access to a Google sheet.
    
    Examples
    --------
    >>> # instance w/ required parameters
    >>> myKey = 'path/to/json/key'
    >>> gs = GymSheet(myKey, 'my_sheet_name')
    """
    
    def __init__(
            self, 
            keyPath: str, 
            sheetName: str, 
            verbose: Optional[bool] = False
            ) -> None:
        """
        Parameters
        ----------
        keyPath: 
            The path to json key required for API access.
        sheetName: 
            The name of Google Sheet with data.
        verbose:
            Print progress statements.
        """

        self.verbose = verbose
        self._retrieve_data(keyPath, sheetName)
        self.errors = list()


    def _retrieve_data(
            self, 
            keyPath: str, 
            sheetName: str
            ) -> None:
        """
        Partition sheet records to category dataframes.
        This method is only called at initialization.

        See Also
        --------
        gspread.worksheet.Worksheet
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
    
    
    def find(
            self, 
            inTitle: str, 
            isUpdate: Optional[bool] = False
            ) -> tuple[str, int]:
        """
        Locates title within database and corrects title if necessary.
        
        Parameters
        ----------
        inTitle:
            The title to locate.
        isUpdate:
            Specifies if inTitle's data is an update.

        Returns
        -------
        outTitle:
            The title from database.
        rowIndex:
            The row index for title.
        
        Exceptions
        ----------
        TitleNotFound if title search unsuccessful.
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
        elif matches.shape[0] > 1:  # Multiple matches.
            outTitle = matches.iat[0,1]
            columns  = ['title','latlon','city','state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter correct INDEX:\t'
            rowIndex   = int(input(prompt))
            if rowIndex not in matches.index:
                raise TitleNotFound
            
        if rowIndex == -1:
            self.errors.append('TITLE')
        
        return outTitle, rowIndex


    def find_from_input(
            self, 
            isUpdate: Optional[bool] = True
            ) -> tuple[str, int]:
        """
        Helper method to GymSheet.find relying on user input.
        
        Parameters
        ----------
        isUpdate:
            Specifies if inTitle's data is an update.

        Returns
        -------
        outTitle:
            The title from database.
        rowIndex:
            The row index for title.
        
        Exceptions
        ----------
        TitleNotFound if title search unsuccessful.
        """
        
        prompt = 'Enter correct TITLE for badge:\n   '
        title = input(prompt).strip()

        outTitle, rowIndex = self.find(title, isUpdate=isUpdate)
        if rowIndex == -1:
            raise TitleNotFound

        return outTitle, rowIndex


    def write_row(
            self, 
            rowIndex: int, 
            rowData: dict
            ) -> None:
        """
        Fill sheet row with new values.
        
        Parameters
        ----------
        rowIndex:
            The row index to write in google sheet.
        rowData:
            The row data as a dictionary.

        See Also
        --------
        gspread.worksheet.Worksheet
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
        Sort sheet contents geographically.
        
        See Also
        --------
        gspread.worksheet.Worksheet
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
