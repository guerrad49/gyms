# standard libraries
import os
import re
import sys
#import logging    # maintain logs
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
    MIN_SIMILARITY = 0.9
    
    def __init__(self, key, sheetname):
        self.establish_connetion(key)
        self.set_data(sheetname)


    def establish_connetion(self, key):
        """Connect with google API"""

        credentials = SAC.from_json_keyfile_name(key, self.SCOPE)
        self.client = gspread.authorize(credentials)
        print('INFO - Connection to Google Drive successful.')


    def set_data(self, sheetname):
        """Extract sheet as dataframe"""

        self.sheet    = self.client.open(sheetname).sheet1
        self.df       = pd.DataFrame(self.sheet.get_all_records())
        # data starts at sheet row 2
        self.df.index = np.arange(2, len(self.df) + 2)
        print('INFO - Data extract successful.')

    
    def split(self):
        """Split main DataFrame between images scanned vs not"""

        self.scanned     = self.df[self.df['image'] != '']
        self.not_scanned = self.df[self.df['image'] == '']
    
    
    def find(self, img_name: str, title: str):
        """
        Locate index of a given title in the database
        
        Parameters
        ----------
        img_name: str
            The full name of image to locate
        title: str
            The title to locate

        Returns
        -------
        tuple(row_idx, similar_title)
        row_idx: int
            The exact row location
        similar_title: str
            The true title in the database
        """

        similar_title = ""
        matches = self.not_scanned[self.not_scanned['title'] == title]

        # check similar titles when no exact match
        if matches.shape[0] == 0:
            matches = self.df[self.df['title']
                    .apply(lambda x: self.is_similar(x, title))
                    ]
            similar_title = matches.iat[0,1]
        
        # check when multiple matches
        if matches.shape[0] > 1:
            columns  = ['title','coordinates','city','state']
            prompt   = 'Duplicates found.\n'
            prompt  += matches[columns].to_string()
            prompt  += '\nEnter INDEX for {}:\t'.format(img_name)
            row_idx  = int(input(prompt))
            if row_idx not in matches.index:
                ColorPrint('error: invalid index value given').fail()
                sys.exit(0)
        else:
            row_idx = matches.index[0]
        
        return (row_idx, similar_title)
    

    def is_similar(self, x: str, y: str) -> bool:
        """Compute similarity percentage between two strings"""

        # NOTE: For short strings, use may want to decrease MIN_SIMILARITY
        likeness = SequenceMatcher(None, x, y).ratio()

        if likeness >= self.MIN_SIMILARITY:
            prompt = 'Found similar match \'{}\'. Accept? (y/n)\t'.format(x)
            response = input(prompt)
            if response == 'y':
                return True
            else:
                return False

        return False


    def write_row(self, row_num, data):
        old_row = 'A{0}:M{0}'.format(row_num)
        self.sheet.update(old_row, data)
        print('Writing to row {}'.format(row_num))
        print(data)


    def sort_by_location(self):
        prompt   = 'Ready to sort spreadsheet? (y/n)  '
        response = input(prompt)

        if response == 'y':
            by_city   = (8,'asc')
            by_county = (9,'asc')
            by_state  = (10,'asc')
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
