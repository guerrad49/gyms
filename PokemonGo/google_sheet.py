import gspread
import numpy as np
import pandas as pd

from typing import Optional

from .utils import are_similar
from .exceptions import InputError


class GoogleSheet:
    """A class for handling reading/writing to a google sheet."""
    
    def __init__(self, keyPath: str, sheetName: str) -> None:
        """
        Parameters
        ----------
        keyPath: 
            The path to json key required for API access
        sheetName: 
            The name of Google Sheet with data
        """

        self.retrieve_data(keyPath, sheetName)


    def retrieve_data(self, keyPath: str, sheetName: str) -> None:
        """Partition sheet records to category dataframes."""

        client     = gspread.service_account(keyPath)
        self.sheet = client.open(sheetName).sheet1
        records    = self.sheet.get_all_records()
        df         = pd.DataFrame(records)
        df.index   = np.arange(2, len(df) + 2)    # start at row 2

        self.processed   = df[df['image'] != '']
        self.unprocessed = df[df['image'] == '']
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
            columns  = ['title','coordinates','city','state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter correct INDEX:\t'
            rowNum   = int(input(prompt))
            if rowNum not in matches.index:
                raise InputError
        else:
            rowNum = matches.index[0]
        
        return title, rowNum


    def write_row(self, rowNum: int, data: list):
        """
        Fill sheet row with new data.
        
        Parameters
        ----------
        rowNum:
            The row number to write in google sheet
        data:
            The content values to write
        """

        oldRow = 'A{0}:M{0}'.format(rowNum)
        self.sheet.update(oldRow, [data])
        
        print('Writing to row {}'.format(rowNum))
        print(data)


    def sort_by_location(self):
        """Optional sort of sheet contents geographically."""

        prompt = 'Ready to sort spreadsheet? (y/n)\t'
        if input(prompt) != 'y':
            return None
        
        cols = self.sheet.row_values(1)   # column titles

        # (column index, 'ascending')
        byCity   = (cols.index('city')   + 1, 'asc')
        byCounty = (cols.index('county') + 1, 'asc')
        byState  = (cols.index('state')  + 1, 'asc')
        
        rowLen = 'A2:M{}'.format(self.sheet.row_count)

        self.sheet.sort(
            byState, byCounty, byCity, 
            range=rowLen
            )
        print('INFO - Sorting complete.\n')