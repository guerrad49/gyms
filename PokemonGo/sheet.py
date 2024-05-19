"""
PokemonGo.sheet
----------------------

This module contains the GymSheet class which extends the 
`gspread` package to manage a Google sheet containing PokemonGo 
data. Data from Google sheet is accessed as pandas.DataFrames.

See Also
--------
gspread
README - instructions on how to generate json key
"""


from typing import Optional

import numpy as np
import pandas as pd
from gspread import service_account

from .gym import GoldGym
from .exceptions import InputError
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
    
    def __init__(self, keyPath: str, sheetName: str) -> None:
        """
        Parameters
        ----------
        keyPath: 
            The path to json key required for API access
        sheetName: 
            The name of Google Sheet with data
        """

        self._retrieve_data(keyPath, sheetName)
        self.errors = list()


    def _retrieve_data(self, keyPath: str, sheetName: str) -> None:
        """
        Partition sheet records to category dataframes.
        This method is only called at initialization.
        """

        client     = service_account(keyPath)
        self.sheet = client.open(sheetName).sheet1
        records    = self.sheet.get_all_records()
        df         = pd.DataFrame(records)
        df.index   = np.arange(2, len(df) + 2)    # start at row 2

        self.processed   = df[df['uid'] != '']
        self.unprocessed = df[df['uid'] == '']
        print('INFO - Data extract successful.')
    
    
    def find(
            self, 
            title: str, 
            new:   Optional[bool] = True
            ) -> tuple[str, int]:
        """
        Locates title within database and corrects title if necessary.
        
        Parameters
        ----------
        title:
            The title to locate
        new:
            The truth value whether title corresponds to new GoldGym

        Returns
        -------
        title:
            The true title in database
        rowNum:
            The row index for title match
        """

        if new:
            df = self.unprocessed
        else:
            df = self.processed
        
        matches = df[df['title'] == title]
        self.errors.clear()

        # check similar titles when no exact match
        if matches.shape[0] == 0:
            matches = df[df['title']
                    .apply(lambda x: are_similar(x, title))
                    ]
        
        # still no similar titles require user input
        if matches.shape[0] == 0:
            matches = self._find_from_input(title, df)

        title = matches.iat[0,1]   # true title
        
        # multiple matches
        if matches.shape[0] > 1:
            columns  = ['title', 'latlon', 'city', 'state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter correct INDEX:\t'
            rowNum   = int(input(prompt))
            if rowNum not in matches.index:
                raise InputError
        else:
            rowNum = matches.index[0]
        
        return title, rowNum


    def _find_from_input(
            self, 
            title: str, 
            df:    pd.DataFrame
            ) -> pd.DataFrame:
        """
        Helper method to GymSheet.find relying on user input.
        
        Parameters
        ----------
        df:
            The DataFrame to search in

        Returns
        -------
        matches:
            The DataFrame with all title matches
        """
        
        self.errors.append('TITLE')
        prompt = 'Enter correct TITLE for `{}`:\t'.format(title)
        inText = input(prompt).strip()
        matches = df[df['title']
            .apply(lambda x: are_similar(x, inText))
            ]
        
        if matches.shape[0] == 0:
            raise InputError
        
        return matches


    def write_row(self, rowNum: int, gymObj: GoldGym) -> None:
        """
        Fill sheet row with new Gym values.
        
        Parameters
        ----------
        rowNum:
            The row number to write in google sheet
        gymObj:
            The Gym which values will be used

        Examples
        --------
        >>> type(someGym)
        <class 'PokemonGo.gym.GoldGym'>
        >>> # write to row 10 in Google Sheet
        >>> gs.write_row(10, someGym)
        """

        # get Gym values needed
        newVals = [
            v for k,v in vars(gymObj).items()
            if k not in ['address', 'errors']
        ]

        # newVals -> A:N is one-to-one mapping
        oldRow = 'A{0}:N{0}'.format(rowNum)
        self.sheet.update(oldRow, [newVals])
        
        print('Writing to row {}'.format(rowNum))
        print(newVals)


    def geo_sort(self) -> None:
        """Sort sheet contents geographically."""
        
        cols = self.sheet.row_values(1)   # column titles

        # (column index, 'ascending')
        byCity   = (cols.index('city')   + 1, 'asc')
        byCounty = (cols.index('county') + 1, 'asc')
        byState  = (cols.index('state')  + 1, 'asc')
        
        rowLen = 'A2:M{}'.format(self.sheet.row_count)

        # sort by state, then county, then city
        self.sheet.sort(
            byState, byCounty, byCity, 
            range=rowLen
            )
        print('INFO - Sorting complete.\n')