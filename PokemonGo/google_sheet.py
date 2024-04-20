# standar libraries
import sys
from difflib import SequenceMatcher

# third-party
import gspread
import numpy as np
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials as SAC


class GoogleSheet:
    '''A class for handling reading/writing to a google sheet'''
    
    SCOPE = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
            ]
    SIMILARITY_MIN = 0.9
    
    def __init__(self, key: str, sheetname: str):
        '''
        Parameters
        ----------
        key: 
            The path to json key required for API access
        sheetname: 
            The name of Google Sheet with data
        '''

        self.key = key
        self.sheetname = sheetname


    def establish_connection(self):
        '''Establish google API access'''

        credentials = SAC.from_json_keyfile_name(self.key, self.SCOPE)
        self.client = gspread.authorize(credentials)
        print('INFO - Connection to Google Drive successful.')


    def records_to_dataframes(self):
        '''Partition sheet records to category dataframes'''

        self.sheet = self.client.open(self.sheetname).sheet1
        df         = pd.DataFrame(self.sheet.get_all_records())
        df.index   = np.arange(2, len(df) + 2)    # start at row 2

        self.processed   = df[df['image'] != '']
        self.unprocessed = df[df['image'] == '']
        print('INFO - Data extract successful.')
    
    
    def find(self, title: str, df: pd.DataFrame) -> tuple[str, int]:
        '''
        Locate given title within database.
        
        Parameters
        ----------
        title: 
            The title to locate
        df:
            The dataframe to search over

        Returns
        -------
        title:
            The true title in database
        row_num:
            The row index for title match
        '''

        matches = df[df['title'] == title]

        # check similar titles when no exact match
        if matches.shape[0] == 0:
            matches = df[df['title']
                    .apply(lambda x: self.is_similar(x, title))
                    ]
            title = matches.iat[0,1]   # true title
        
        # check when multiple matches
        if matches.shape[0] > 1:
            columns  = ['title','coordinates','city','state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter correct INDEX:\t'
            row_num  = int(input(prompt))
            if row_num not in matches.index:
                # TODO: had access to ColorPrint
                print('error: invalid index value given')
                sys.exit()
        else:
            row_num = matches.index[0]
        
        return title, row_num
    

    def is_similar(self, x: str, y: str) -> bool:
        '''Compute similarity percentage between two strings'''

        # WARNING: For short strings, user may want to decrease SIMILARITY_MIN
        likeness = SequenceMatcher(None, x, y).ratio()

        if likeness >= self.SIMILARITY_MIN:
            prompt = 'Found similar match \'{}\'. Accept? (y/n)\t'.format(x)
            if input(prompt) == 'y':
                return True
            else:
                return False

        return False


    def write_row(self, row_num: int, data: list):
        '''
        Fill sheet row with new data.
        
        Parameters
        ----------
        row_num:
            The row number to write in google sheet
        data:
            The content values to write
        '''

        old_row = 'A{0}:M{0}'.format(row_num)
        self.sheet.update(old_row, [data])
        
        # sanity check
        print('Writing to row {}'.format(row_num))
        print(data)


    def sort_by_location(self):
        '''Optional sort of sheet contents geographically'''

        prompt = 'Ready to sort spreadsheet? (y/n)  '

        if input(prompt) == 'y':
            by_city   = (11,'asc')
            by_county = (12,'asc')
            by_state  = (13,'asc')
            row_len = 'A2:M{}'.format(self.sheet.row_count)

            self.sheet.sort(
                by_state, by_county, by_city, 
                range=row_len
                )
            print('INFO - Sorting complete.\n')