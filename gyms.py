#!/usr/bin/env python3

# standard libraries
import os
import re
import sys
import pdb        # debugger
#import logging    # maintain logs
import argparse
#from difflib import SequenceMatcher

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

VARIABLES = 'variables.env'
DOWNLOADS = os.path.join(os.getenv('HOME'), 'Downloads')
BADGES    = os.path.join(os.getcwd(), 'badges')


#===============================SHEET CLASS===================================

class GoogleSheet:
    SCOPE = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
            ]
    
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

    
    def partition(self):
        self.scanned      = self.df[self.df['image'] != '']
        self.not_scanned  = self.df[self.df['image'] == '']
        self.available_id = self.scanned['image'].max() + 1

    
    def locate_by_name(self, title) -> int:
        matches = self.df[self.df['title'] == title]
        
        # check for duplicate titles
        if matches.shape[0] > 1:
            columns = ['title','coordinates','city','state']
            prompt  = 'Duplicates found.\n'
            prompt += matches[columns].to_string()
            prompt += '\nEnter INDEX for {}:\t'.format(self.id)
            ridx    = int(input(prompt))
        else:
            ridx = matches.index[0]
        
        return ridx


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
    SCALE_FACTOR = 1.75
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


    def best_txt(self, img=None):
        '''Pre-process image and extract text'''

        if img is None:
            img = self.image
        
        h1 = round(img.shape[0] * self.SCALE_FACTOR)
        w1 = round(img.shape[1] * self.SCALE_FACTOR)
        resized   = cv2.resize(img, (w1, h1))
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(grayscale, 200, 230, cv2.THRESH_BINARY)

        return pytesseract.image_to_string(thresh)


    def get_title_txt(self):
        '''Extract image title from predetermined crop'''

        cropped = self.image[50:140, 0:self.image.shape[1]]
        txt = self.best_txt(cropped)

        # string clean up
        txt = txt.replace("’", "'")
        txt = txt.replace('\n', ' ')

        return txt.strip().lower()


    def get_stats_info(self):
        '''Extract image stats from predetermined crop'''

        cropped = self.image[975:1100, 0:self.image.shape[1]]
        txt = self.best_txt(cropped)
        txt = txt.replace('O', '0')   # string clean up

        match = re.search(self.STATS_RE_PAT, txt)
        if match == None:
            return None
        else:
            return match.groupdict()


#================================GYM CLASS====================================

class GymClass:
    STYLE_MIN = 100

    def __init__(self, ridx, img_vals, coords):
        self.ridx = ridx
        self.set_title(img_vals)
        self.set_victories(img_vals)
        self.set_time_defended(img_vals)
        self.set_treats(img_vals)
        self.set_style()
        self.set_address(coords)
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
        if self.days >= self.STYLE_MIN:
            self.style = '100+ days'
        else:
            self.style = 'gold'

    def set_address(self, coordinates):
        coords       = coordinates.split(',')
        geolocator   = Nominatim(user_agent=AGENT)   # required by ToS
        location     = geolocator.reverse(coords)
        self.address = location.raw['address']

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

    def describe(self):
        d = vars(self)
        del d['address']
        return d
    

#=============================PROCESSOR CLASS=================================

class Processor:
    def __init__(self, mode):        
        if not self.has_queue_to_set():
            ColorPrint('---Processor ended---\n').fail()
            sys.exit(0)
        
        self.mode = mode


    def has_queue_to_set(self) -> bool:
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
        gs.partition()

        ColorPrint('\nINFO - Begin scanning process.\n').proc()

        for file in self.queue:
            img_data = dict()
            img = ImageClass(file)
            img_data['title'] = img.get_title_txt()
            stats = img.get_stats_info()

            if stats is None:
                pass
            else:
                img_data.update(stats)

            idx = gs.locate_by_name(img_data['title'])
            g = GymClass(idx, img_data, gs.df.at[idx,'coordinates'])
            sheet_row = g.describe()
            print(sheet_row)
            print()





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
    subdir = os.path.join(os.getcwd(), 'subfiles')

    global KEYFILE, SHEET, AGENT
    error_prompt = "error: could not locate '{}' file"
    
    # load environment
    env_path = os.path.join(subdir, VARIABLES)
    load_dotenv(env_path)
    
    # check json key file exits
    KEYFILE = os.path.join(subdir, os.getenv("KEYFILE"))
    if not os.path.isfile(KEYFILE):
        ColorPrint(error_prompt.format(KEYFILE)).fail()
        return False
    
    # set remainding environment values
    SHEET = os.getenv("SHEET_NAME")
    AGENT = os.getenv("EMAIL")

    return True


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
    p.run_scanner()