# standard libraries
import os
import re
import sys
#import logging    # maintain logs
from typing import Tuple
from difflib import SequenceMatcher

# third-party packages
import cv2               # image reading
import pytesseract       # packages for reading
import numpy as np
import pandas as pd

import gspread
from geopy.geocoders import Nominatim
from oauth2client.service_account import ServiceAccountCredentials as SAC


#===============================SHEET CLASS===================================

class GoogleSheet:
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
    
    
    def find(self, title: str, df: pd.DataFrame) -> Tuple[str, int]:
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
                ColorPrint('error: invalid index value given').fail()
                sys.exit(0)
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
        self.sheet.update(old_row, data)
        
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
            row_len = 'A2:J{}'.format(self.sheet.row_count)

            self.sheet.sort(
                by_state, by_county, by_city, 
                range=row_len
                )
            print('INFO - Sorting complete.\n')


#===============================IMAGE CLASS===================================

class Image:
    STATS_RE_PAT = re.compile(r"""
        .+TREATS
        [\n\ ]+
        (?P<victories>\d{1,4})           # victories
        [\n\ ]+
        ((?P<days>\d{1,3})d[\ ]?)?       # days
        ((?P<hours>\d{1,2})h[\ ]?)?      # hours
        ((?P<minutes>\d{1,2})m[\ ]?)?    # minutes
        ((\d{1,2})s)?                    # seconds (very rare)
        [\n\ ]+
        (?P<treats>\d{1,4})              # treats
        """, re.X|re.S)


    def __init__(self, filepath):
        self.filepath = filepath
        self.image    = cv2.imread(filepath)
        self.set_params()

    
    def set_params(self):
        dimensions = self.image.shape[:2]
        
        if dimensions == (1334, 750):   # iPhone SE
            self.scale = 1.75
            self.title_start = 50
            self.title_end   = 140
            self.stats_start = 975
            self.stats_end   = 1100
        elif dimensions == (1792, 828):   # iPhone 11
            self.scale = 1.5
            self.title_start = 60
            self.title_end   = 150
            self.stats_start = 1075
            self.stats_end   = 1225
        elif dimensions == (2556, 1179):   # iPhone 15
            self.scale = 1
            self.title_start = 110
            self.title_end   = 210
            self.stats_start = 1550
            self.stats_end   = 1800
        else:
            ColorPrint('error - model unavailable').warning()
            sys.exit()


    def best_txt(self, img=None) -> str:
        '''Pre-process image and extract text'''

        if img is None:
            img = self.image
        
        h1 = round(img.shape[0] * self.scale)
        w1 = round(img.shape[1] * self.scale)
        resized   = cv2.resize(img, (w1, h1))
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(grayscale, 200, 230, cv2.THRESH_BINARY)

        return pytesseract.image_to_string(thresh)


    def get_title_txt(self) -> str:
        '''Extract image title from predetermined crop'''

        cropped = self.image[
            self.title_start:self.title_end, 
            0:self.image.shape[1]
            ]
        txt = self.best_txt(cropped)

        # string clean up
        txt = txt.replace("’", "'")
        txt = txt.replace('\n', ' ')

        return txt.strip().lower()


    def get_stats_info(self):
        '''Extract image stats from predetermined crop'''

        cropped = self.image[
            self.stats_start:self.stats_end, 
            0:self.image.shape[1]
            ]
        txt = self.best_txt(cropped)
        txt = txt.replace('O', '0')   # string clean up

        match = re.search(self.STATS_RE_PAT, txt)
        if match == None:
            return None
        else:
            return match.groupdict()
        
    
    def to_storage(self, storage_dir, new_id):
        """Move image file to storage with a new id"""
    
        new_name = 'IMG_{:04d}.PNG'.format(new_id)
        new_path = os.path.join(storage_dir, new_name)
        os.rename(self.filepath, new_path)
        self.filepath = new_path

        ColorPrint('INFO - Image successfully relocated.').proc()


#================================GYM CLASS====================================

class Gym:
    LONG_TERM_DEFENDING = 100   # in days

    def __init__(self, img_id, data, loc, email):
        self.image = int(img_id)
        self.set_title(data)
        self.set_victories(data)
        self.set_time_defended(data)
        self.set_treats(data)
        self.set_style()
        self.set_address(loc, email)
        self.set_city()
        self.set_county()
        self.set_state()

    def set_title(self, d):
        self.title = d['title']

    def set_victories(self, d):
        self.victories = int(d['victories'])

    def set_time_defended(self, d):
        subd = {k:d[k] for k in ['days','hours','minutes']}
        subd = {k:0 if v is None else int(v) for k,v in subd.items()}
        
        self.days    = subd['days']
        self.hours   = subd['hours']
        self.minutes = subd['minutes']
        
        total = self.days + self.hours / 24 + self.minutes / 1440
        self.defended = round(total, 4)

    def set_treats(self, d):
        self.treats = int(d['treats'])

    def set_style(self):
        if self.days >= self.LONG_TERM_DEFENDING:
            self.style = '100+ days'
        else:
            self.style = 'gold'

    def set_address(self, coordinates, agent):
        self.coordinates  = coordinates
        geolocator        = Nominatim(user_agent=agent)   # required by ToS
        location          = geolocator.reverse(self.coordinates.split(','))
        self.address      = location.raw['address']

    def set_city(self):
        city = None

        # most commonly observed options
        for option in ['city','town','village','township']:
            try:
                city = self.address[option]
                break
            except KeyError:
                pass
 
        if city is None:
            # city = self.log_error('City')
            city = ''
        
        self.city = city.lower()

    def set_county(self):
        try:
            county = self.address['county']
        except KeyError:
            # county = self.log_error('County')
            county = ''
        else:
            county = re.search('.*(?= County)', county).group(0)

        self.county = county.lower()

    def set_state(self):
        self.state = self.address['state'].lower()

    def format_vars(self):
        """Construct formatted row"""

        row = [
            self.image, 
            self.title, 
            self.style, 
            self.victories, 
            self.days, 
            self.hours, 
            self.minutes, 
            self.defended, 
            self.treats, 
            self.coordinates, 
            self.city, 
            self.county, 
            self.state
            ]

        return [row]
    

#================================PRINT CLASS==================================

class ColorPrint:
    OKCYAN    = '\033[96m'
    WARNING   = '\033[93m'
    OKGREEN   = '\033[92m'
    FAIL      = '\033[91m'
    BOLD      = '\033[1m'
    ENDC      = '\033[0m'

    def __init__(self, msg):
        self.msg = msg

    def proc(self):
        print('{}{}{}'.format(self.OKCYAN, self.msg, self.ENDC))

    def ok(self):
        print('{}{}{}'.format(self.OKGREEN, self.msg, self.ENDC))

    def warning(self):
        print('{}{}{}'.format(self.WARNING, self.msg, self.ENDC))

    def fail(self):
        print('{}{}{}{}'.format(self.FAIL, self.BOLD, self.msg, self.ENDC))


#===============================FUNCTIONS=====================================


def get_formatted_row(d):
    """Construct formatted row"""

    row = [
        d['image'], 
        d['title'], d['style'], 
        d['victories'], 
        d['days'], d['hours'], d['minutes'], 
        d['defended'], 
        d['treats'], 
        d['coordinates'], 
        d['city'], d['county'], d['state']
        ]

    return [row]
