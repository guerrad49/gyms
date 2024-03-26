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

import pytesseract       # packages for reading
from PIL import Image    # and enhancing images

from geopy.geocoders import Nominatim
from oauth2client.service_account import ServiceAccountCredentials as SAC


#=============================GLOBAL VARIABLES================================

VARIABLES = 'variables.env'
DOWNLOADS = os.path.join(os.getenv('HOME'), 'Downloads')


#===============================IMAGE CLASS===================================



class ImageClass:
    STANDARD_SIZE = (750, 1334)
    BOX_TOP = 50
    PATTERN = re.compile(r"""
        .+TREATS
        \n\n
        (?P<victories>\d{1,4})           # victories
        \n\n
        ((?P<days>\d{1,3})d[\ ]?)?       # days defended
        ((?P<hours>\d{1,2})h[\ ]?)?      # hours defended
        ((?P<minutes>\d{1,2})m[\ ]?)?    # minutes defended
        ((\d{1,2})s)?                    # seconds defended (very rare)
        \n\n
        (?P<treats>\d{1,4})              # treats
        """, re.X|re.S)


    def __init__(self, filename):
        """Constructor keeps a copy of image file"""

        with Image.open(filename) as im:
            self.image = im.copy()
        self.as_thumbnail()
        self.cropped()
        self.set_image_text()


    def as_thumbnail(self):
        """Resizes image while keeping aspect ratio"""

        self.image.thumbnail(self.STANDARD_SIZE)


    def cropped(self):
        """Removes mobile headers from image"""

        box_right  = self.image.size[0]
        box_bottom = self.image.size[1]
        box = (0, self.BOX_TOP, box_right, box_bottom)
        self.image = self.image.crop(box)


    def set_image_text(self):
        """Extracts text from image"""

        my_config = r'--psm 12'
        txt = pytesseract.image_to_string(self.image, config=my_config)
        self.img_txt = txt


    def parse_image_text(self):
        """Parses image text using regex"""

        match = re.search(self.PATTERN, self.img_txt)

        if match == None:
            return None
        else:
            return match.groupdict()


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

        key_path    = os.path.join(SUBDIR, KEYFILE)
        credentials = SAC.from_json_keyfile_name(key_path, self.SCOPE)
        self.client = gspread.authorize(credentials)
        print('INFO - Connection to Google Drive successful.')


    def set_data(self):
        """Extract sheet as dataframe"""

        self.sheet    = self.client.open(SHEET).sheet1
        self.df       = pd.DataFrame(self.sheet.get_all_records())
#        self.df.index = np.arange(2, len(self.df) + 2)
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
        pass

    def set_victories(self, d):
        self.victories = int(d['victories'])

    def set_time_defended(self, d):
        d = {k:0 if v is None else int(v) for k,v in d.items()}
        
        self.days    = d['days']
        self.hours   = d['hours']
        self.minutes = d['minutes']
        
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
        print(prompt)
        print()
        return True
    
    
    def run_scanner(self):
        gs = GoogleSheet()
        gs.partition()

        ColorPrint('\nINFO - Begin scanning process.\n').proc()

        for i in [30,848,849,1183,1184]:
            name = 'IMG_{:04d}.PNG'.format(i)
            full_path = os.path.join(BADGES, name)
            img = ImageClass(full_path)
            data = img.parse_image_text()

            if data is None:
                continue

#            idx = gs.locate_by_name(data['title'])
            coords = gs.df[gs.df['image']==i].iat[0,6]
            g = GymClass(i, data, coords)
            row = g.describe()
            print(row)
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


def has_valid_structure():
    global SUBDIR, BADGES
    error_prompt = "error: could not locate '{}' directory"

    # check 'subfiles' is in tree structure
    SUBDIR = os.path.join(os.getcwd(), 'subfiles')
    if not os.path.isdir(SUBDIR):
        ColorPrint(error_prompt.format(SUBDIR)).fail()
        return False
    
    # check 'badges' is in tree structure
    BADGES = os.path.join(os.getcwd(), 'badges')    
    if not os.path.isdir(BADGES):
        ColorPrint(error_prompt.format(BADGES)).fail()
        return False
    
    return True

def has_valid_environment():
    global KEYFILE, SHEET, AGENT
    error_prompt = "error: could not locate '{}' file"

    # check 'variables.env' exists
    if VARIABLES not in os.listdir(SUBDIR):
        ColorPrint(error_prompt.format(VARIABLES)).fail()
        return False
    
    # load environment
    env_path = os.path.join(SUBDIR, VARIABLES)
    load_dotenv(env_path)
    
    # check json key file exits
    KEYFILE = os.getenv("KEYFILE")
    if KEYFILE not in os.listdir(SUBDIR):
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

    if not has_valid_structure():
        sys.exit(0)
    
    if not has_valid_environment():
        sys.exit(0)
    
    p = Processor(args.scan)
    p.run_scanner()