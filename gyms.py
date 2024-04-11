#!/usr/bin/env python3

# standard libraries
import os
import re
import sys
import pdb        # debugger
#import logging    # maintain logs
import argparse
from difflib import SequenceMatcher

# third-party packages
import gspread
import numpy as np
import pandas as pd
from dotenv import load_dotenv    # load env vars

import cv2
import pytesseract       # packages for reading
from PIL import Image    # and enhancing images

from geopy.geocoders import Nominatim
from oauth2client.service_account import ServiceAccountCredentials as SAC


#=============================GLOBAL VARIABLES================================

DOWNLOADS = os.path.join(os.getenv('HOME'), 'Downloads')
BADGES    = os.path.join(os.path.dirname(__file__), 'badges')

#===============================SHEET CLASS===================================

class GoogleSheet:
    SCOPE = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
            ]
    MIN_SIMILARITY = 0.9
    
    def __init__(self):
        self.establish_connetion()
        self.set_data()


    def establish_connetion(self):
        """Connect with google API"""

        credentials = SAC.from_json_keyfile_name(KEYFILE, self.SCOPE)
        self.client = gspread.authorize(credentials)
        print('INFO - Connection to Google Drive successful.')


    def set_data(self):
        """Extract sheet as dataframe"""

        self.sheet    = self.client.open(SHEET).sheet1
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

class ImageClass:
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


    def __init__(self, filename):
        self.image = cv2.imread(filename)
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


#================================GYM CLASS====================================

class GymClass:
    LONG_TERM_DEFENDING = 100   # in days

    def __init__(self, img_id, data, loc):
        self.image = int(img_id)
        self.set_title(data)
        self.set_victories(data)
        self.set_time_defended(data)
        self.set_treats(data)
        self.set_style()
        self.set_address(loc)
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

    def set_address(self, coordinates):
        self.coordinates  = coordinates
        geolocator        = Nominatim(user_agent=AGENT)   # required by ToS
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
    

#=============================PROCESSOR CLASS=================================

class Processor:
    def __init__(self, mode):        
        self.mode = mode


    def has_queue(self) -> bool:
        """Returns True when successfully populated a queue to scan"""

        self.queue = [
            os.path.join(DOWNLOADS, x) for x in os.listdir(DOWNLOADS) \
            if x.endswith('.PNG')
            ]

        if len(self.queue) == 0:
            print('INFO - No images found.\n')
            return False
        
        prompt  = 'INFO - Found the following images:\n'
        prompt += '\n'.join(self.queue)
        prompt += '\n'
        print(prompt)
        return True
    
    
    def run_scanner(self):
        gs = GoogleSheet()
        gs.split()
        next_id = gs.scanned['image'].max() + 1

        ColorPrint('\nINFO - Begin scanning process.\n').proc()

        for path in self.queue:
            img_data = dict()
            img = ImageClass(path)
            img_data['title'] = img.get_title_txt()
            stats = img.get_stats_info()
            img_data.update(stats)

            ridx, title_from_df = gs.find(path, img_data['title'])

            coords = gs.df.at[ridx,'coordinates']
            if title_from_df != "":
                img_data['title'] = title_from_df
            g = GymClass(next_id, img_data, coords)

            gym_row = get_formatted_row(vars(g))
            print(gym_row)
            # gs.write_row(ridx, gym_row)
            # print()



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

def has_valid_environment():
    subfiles = os.path.join(os.path.dirname(__file__), 'subfiles')

    # load environment
    env_path = os.path.join(subfiles, 'variables.env')
    load_dotenv(env_path)
    
    global KEYFILE, SHEET, AGENT
    
    # check json key file exits
    KEYFILE = os.path.join(subfiles, os.getenv("KEYFILE"))
    if not os.path.isfile(KEYFILE):
        prompt = "error: could not locate '{}' file".format(KEYFILE)
        ColorPrint(prompt).fail()
        return False
    
    # check remainding env variables
    prompt = "error: 'variables.env' not properly set"

    if (SHEET := os.getenv("SHEET")) == "":
        ColorPrint(prompt).fail()
        return False
    
    if (AGENT := os.getenv("EMAIL")) == "":
        ColorPrint(prompt).fail()
        return False

    return True


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


def parse_args():
    command_desc = 'Scan badge data from PNG files.'
    p = argparse.ArgumentParser(description=command_desc)

    flags = p.add_mutually_exclusive_group()
    flags.add_argument('-s', '--scan', action='store_true',
        help='scan new badges')
    flags.add_argument('-u', '--update', action='store_true',
        help='update badge given')

    args = p.parse_args()
            
    return args


#==================================MAIN=======================================


if __name__ == "__main__":
    args = parse_args()

    if not has_valid_environment():
        sys.exit(0)
    
    p = Processor(args.scan)
    if not p.has_queue():
        ColorPrint('---Processor ended---\n').fail()
        sys.exit(0)

    p.run_scanner()