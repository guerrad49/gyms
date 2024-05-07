"""
PokemonGo.google_sheet
----------------------

This module contains the GoogleSheet class which extends 
the `gspread` library for our specific purposes. Data from 
Google Sheets is accessed locally as pd.DataFrames. The 
methods used as motivation for this class are:
    1. self.find
    2. self.write_row

All connections to Google are handled automatically.

See Also
--------
gspread
"""


import gspread
import numpy as np
import pandas as pd

from typing import Optional

from .utils import are_similar
from .gym import GoldGym
from .exceptions import InputError


class GoogleSheet:
    """
    An instance of this class handles access to a Google Sheet.
    
    Examples
    --------
    >>> # instance w/ required parameters
    >>> myKey = 'path/to/json/key'    # valid path
    >>> gs = GoogleSheet(myKey, 'my_sheet_name')
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


    def _retrieve_data(self, keyPath: str, sheetName: str) -> None:
        """
        Partition sheet records to category dataframes.
        This method is only called at initialization.
        """

        client     = gspread.service_account(keyPath)
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
            new: Optional[bool] = True
            ) -> tuple[str, int]:
        """
        Locates title within database and corrects title if necessary.
        
        Parameters
        ----------
        title:
            The title to locate
        new:
            The truth value whether title corresponds to new Gym

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

        # check similar titles when no exact match
        if matches.shape[0] == 0:
            matches = df[df['title']
                    .apply(lambda x: are_similar(x, title))
                    ]
            title = matches.iat[0,1]   # true title
        
        # check with user when multiple matches
        if matches.shape[0] > 1:
            columns  = ['title','latlon','city','state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter correct INDEX:\t'
            rowNum   = int(input(prompt))
            if rowNum not in matches.index:
                raise InputError
        else:
            rowNum = matches.index[0]
        
        return title, rowNum


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
            if k != 'address'
        ]

        # newVals -> A:M is one-to-one mapping
        oldRow = 'A{0}:M{0}'.format(rowNum)
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