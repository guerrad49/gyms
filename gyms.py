#!/usr/bin/env python3

# standard libraries
import os
import re
import sys
import pdb        # debugger
import logging    # maintain logs
import argparse
from difflib import SequenceMatcher

# third-party packages
import gspread
import numpy as np
import pandas as pd

import pytesseract                     # packages for reading
from PIL import Image, ImageEnhance    # and enhancing images

from geopy.geocoders import Nominatim
from oauth2client.service_account import ServiceAccountCredentials as SAC

#=============================GLOBAL VARIABLES================================

LOG_FORMAT = '%(asctime)s    %(image)12s    %(levelname)s: %(message)s'

SUBFILES_DIR = '/Users/david_guerra/Documents/Programming/python/gyms/subfiles'
VARS_FILE = 'variables.txt'

#TTL_COORDS = (20,65,810,250)         # position in
TTL_COORDS = (20,105,1160,250)         # position in
#VIC_COORDS = (70,1080,290,1220)      # images for
VIC_COORDS = (110,1550,380,1720)      # images for
#DEF_COORDS = (300,1080,520,1220)     # specific
DEF_COORDS = (420,1550,760,1720)     # specific
#TRT_COORDS = (540,1080,750,1220)     # data
TRT_COORDS = (810,1550,1040,1720)     # data

TTL_PAT = re.compile(r"""
((?P<g1>.+)\n{,2})           # title part 1
((?P<g2>.+)\n{,2})?          # title part 2
((?P<g3>.+)\n{,2})?          # title part 3""", re.X)

VIC_PAT = re.compile(r"VICTORIES\n(?P<victories>.{1,4})")

DEF_PAT = re.compile(r"""
.+DEFENDED\n                    # values start after DEFENDED and newline
((?P<days>\d{1,3})d[\ ]?)?      # days defended
((?P<hrs>\d{1,2})h[\ ]?)?       # hours defended
((?P<mins>\d{1,2})m[\ ]?)?      # minutes defended
((?P<secs>\d{1,2})s)?           # seconds defended
\n""", re.X)

TRT_PAT = re.compile(r"TREATS\n(?P<treats>.{1,4})")

# best tested point-threshold values
TTL_THRESH = 199     # 199, 150, 152, 163, 202
DEF_THRESH = 161     # 161, 163, 164, 165, 166
TRT_THRESH = 181     # 181, 182, 183, 184, 185

MIN_SIMILARITY = 0.9

#SAMPLE_START = 849     # should start with 1 for new users

OKCYAN    = '\033[96m'
WARNING   = '\033[93m'
OKGREEN   = '\033[92m'
FAIL      = '\033[91m'
BOLD      = '\033[1m'
ENDC      = '\033[0m'

#================================GYM CLASS====================================

class Gym:
    def __init__(self, filename, dataframe):
        self.fname = filename
        self.set_id()
        self.errors = list()

        self.image = Image.open(filename)
        self.set_title(dataframe)
        self.set_row_index(dataframe)
        self.set_victories()
        self.set_time_defended()
        self.set_treats()
        self.image.close()

        self.set_coordinates(dataframe)
        self.set_address()
        self.set_city()
        self.set_county()
        self.set_state()
        

    def set_id(self):
        """Auto set id conditionally"""
        
        try:
            self.id = int(self.fname[-8:-4])
        except:
            # should only catch non-iphone screenshots
            # value won't be used to update
            self.id = self.fname[-12:-4]


    def set_title(self, df):
        """Set title from Image object"""

        title_img = self.image.crop(TTL_COORDS)
        gray_img  = title_img.convert(mode='L')
        final_img = gray_img.point(lambda x: 255 if x > TTL_THRESH else 0)
        txt       = pytesseract.image_to_string(final_img)
        txt       = txt.replace(chr(8217), chr(39))    # incorrect apostrophe
        match     = re.search(TTL_PAT, txt)

        # error with image processing
        if match == None:
            self.title = self.log_error('Title')
            return None
        
        # attempt to find name without user input
        self.title = None
        attempt    = ''
        match_parts  = match.groupdict().values()
        true_matches = [m.lower() for m in match_parts if m is not None]

        for value in true_matches:
            attempt += ' {}'.format(value)
            attempt  = attempt.strip()
            df_hits  = df[df['title']
                          .apply(lambda x: self.is_similar(x, attempt))
                          ]
            if df_hits.shape[0] > 0:  # LOOK OVER LOGIC
                self.title = df_hits.iat[0,1]   # [0,1] df position
                break

        # user-input required to set title
        if self.title == None:
            self.get_title_with_user_opts(match.groupdict())


    def is_similar(self, x, y):
        """Compare two strings for highest similiarity percentage"""

        # WARNING: 90% will likely be too high for comparing small strings
        likeness = SequenceMatcher(None, x, y).ratio()

        if likeness == 1:
            return True
        elif likeness > MIN_SIMILARITY:
            prompt = 'Found similar match \'{}\'. Accept? (y/n)'.format(x)
            response = input(prompt)
            if response == 'y':
                return True
            else:
                return False
        else:
            return False


    def get_title_with_user_opts(self, match_grps):
        prompt   = 'Is this an update with title change? (y/n)   '
        response = input(prompt)
        if response != 'y':
            ColorPrint('ERROR - Title not found. Check database.\n').fail()
            sys.exit()

        prompt   = 'Badge ID your are updating:   '
        response = input(prompt)
        try:
            response = int(response)
        except ValueError:
            ColorPrint('ERROR - Invalid input.\n').fail()
            sys.exit()
        self.id = response

        prompt  = 'TITLE GROUPS:\n{}\n\n'.format(match_grps)
        prompt += 'Up to which group is the title contained? [1,2,3]\n'
        prompt += 'If NO group contains title, enter 0.   '
        response = input(prompt)
        
        if response == '0':
            self.title = self.log_error('Title')
        else:
            parts = list(match_grps.values())[:response]
            self.title = ' '.join(parts)
        

    def set_row_index(self, df):
        """Set row index from DataFrame"""

        # updating past badge
        if self.id in df['image'].values:
            df_gym   = df[df['image']==self.id]
            self.row = df_gym.index[0]
            return None
        
        # new badge
        condition01 = df['title'] == self.title
        condition02 = df['image'] == ''
        df_gym = df[ (condition01) & (condition02) ]
        
        # check for duplicate titles
        if df_gym.shape[0] > 1:
            columns = ['title','coordinates','city','state']
            prompt  = 'Duplicates found.\n'
            prompt += df_gym[columns].to_string()
            prompt += '\nEnter INDEX for {}:\t'.format(self.id)
            i       = int(input(prompt))
        else:
            i = df_gym.index[0]

        self.row = i
    

    def set_victories(self):
        """Set victories from Image object"""

        vic_img  = self.image.crop(VIC_COORDS)
        gray_img = vic_img.convert(mode='L')
        txt      = pytesseract.image_to_string(gray_img)

        try:
            match = re.search(VIC_PAT, txt)
            vic   = int(match.group('victories'))
        except (ValueError, AttributeError):
            vic = self.log_error('Victories')

        self.victories = int(vic)


    def set_time_defended(self):
        """Set time defended from Image object"""

        def_img      = self.image.crop(DEF_COORDS)
        contrast_img = ImageEnhance.Contrast(def_img).enhance(2)
        gray_img     = contrast_img.convert(mode='L')
        final_img    = gray_img.point(lambda x: 255 if x > DEF_THRESH else 0)
        txt          = pytesseract.image_to_string(final_img)

        try:
            stats = re.search(DEF_PAT, txt).groupdict()
        except AttributeError:
            txt   = 'TIME DEFENDED\n'
            txt  += self.log_error('Time Defended')
            txt  += '\n'
            stats = re.search(DEF_PAT, txt).groupdict()
        finally:
            for key,val in stats.items():
                if val in [None, 'O']:
                    stats[key] = 0
                else:
                    stats[key] = int(val)

        total = stats['days'] + stats['hrs']/24 + stats['mins']/1440 \
            + stats['secs']/86400

        self.defended = round(total, 4)


    def set_treats(self):
        """Set treats from Image object"""

        treat_img = self.image.crop(TRT_COORDS)
        gray_img  = treat_img.convert(mode='L')
        final_img = gray_img.point(lambda x: 255 if x > TRT_THRESH else 0)
        txt       = pytesseract.image_to_string(final_img)

        try:
            match  = re.search(TRT_PAT, txt)
            treats = int(match.group('treats'))
        except (ValueError, AttributeError):
            treats = self.log_error('Treats')

        self.treats = int(treats)
 

    def set_coordinates(self, df):
        """Set coordinates from DataFrame"""

        self.coordinates = df.loc[self.row]['coordinates']


    ###### NOTE: the following methods depend on self.coordinates #####

    def set_address(self):
        """Set address dictionary from coordinates"""

        coords       = self.coordinates.split(',')
        geolocator   = Nominatim(user_agent=AGENT)   # required by ToS
        location     = geolocator.reverse(coords)
        self.address = location.raw['address']
        

    def set_city(self):
        """Set city from address dictionary"""

        city = None

        # most commonly observed options
        for option in ['city','town','village','township']:
            try:
                city = self.address[option]
                break
            except KeyError:
                pass
 
        if city is None:
            city = self.log_error('City')
        
        self.city = city.lower()

    
    def set_county(self):
        """Set county from address dictionary"""

        try:
            county = self.address['county']
        except KeyError:
            county = self.log_error('County')
        else:
            county = re.search('.*(?= County)', county).group(0)

        self.county = county.lower()


    def set_state(self):
        """Set state from address dictionary"""

        self.state = self.address['state'].lower()


    def log_error(self, ename):
        """Routine function for handling similiar error types"""

        self.errors.append(ename.upper())
        prompt = 'ERROR - Enter {} for image {}:'.format(ename, self.id)
        ColorPrint(prompt).warning()
        value  = input()
        return value.lower()


#=============================PROCESSOR CLASS=================================

class Processor:
    def __init__(self, mode, df, sheet_obj):
        self.mode = mode
        
        df_scanned    = df[df['image'] != '']
        self.avail_id = df_scanned['image'].max() + 1

        if self.mode == 'scan':
            self.df = df[df['image'] == '']
        elif self.mode == 'update':
            self.df = df_scanned
        
        self.sheet = sheet_obj
        if not self.has_queue_to_set():
            ColorPrint('---Processor ended---\n').fail()
            sys.exit(0)


    def has_queue_to_set(self):
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
        return True
    

    def run_scanner(self):
        """
        Bulk process of extracting data from images, updating google
        sheets and relocating to proper directory when done.
        """

        ColorPrint('\nINFO - Begin scanning process.\n').proc()

        for path in self.queue:
            g = Gym(path, self.df)
            if self.mode == 'scan':
                g.id = self.avail_id

            new_vals = self.get_formatted_row(vars(g))
            
            old_vals = 'A{0}:J{0}'.format(g.row)
#            self.sheet.update(old_vals, new_vals)

            prompt  = 'INFO - Scan for \"{}\" assigned '.format(g.title)
            prompt += 'ID {} and complete.\n'.format(g.id)
            ColorPrint(prompt).ok()

#            self.relocate_image(path, g.id)
            self.update_log(g)
            self.avail_id += 1
            
            print('\n' + '='*50 + '\n')
        
        ColorPrint('INFO - Scanning complete.\n').proc()


    def get_formatted_row(self, d):
        """Construct formatted row"""

        # 100 days defending is a special achievement
        if d['defended'] >= 100:
            gstyle = '100+ days'
        else:
            gstyle = 'gold'

        row = [
            d['id'], d['title'], gstyle, 
            d['victories'], d['defended'], d['treats'], 
            d['coordinates'],
            d['city'], d['county'], d['state']
            ]

        return [row]
    

    def update_log(self, gym_obj):
        """Write to log file with results from scans"""
    
        name = 'IMG_{:04d}.PNG'.format(gym_obj.id)
        d = {'image': name}

        if gym_obj.errors:
            all_errors = ', '.join(gym_obj.errors)
            logging.debug(all_errors, extra=d)
        else:
            logging.info('No errors', extra=d)


    def relocate_image(self, cur_path, update_id):
        """Move and rename file from downloads to badges folder"""
    
        if self.mode == 'scan':
            new_name = 'IMG_{:04d}.PNG'.format(self.avail_id)
        else:     # update
            new_name = 'IMG_{:04d}.PNG'.format(update_id)

        new_path = os.path.join(BADGES, new_name)
        os.rename(cur_path, new_path)

        ColorPrint('INFO - Image successfully relocated.').proc()


#================================PRINT CLASS===================================

class ColorPrint:
    def __init__(self, msg):
        self.msg = msg

    def proc(self):
        print('{}{}{}'.format(OKCYAN, self.msg, ENDC))

    def ok(self):
        print('{}{}{}'.format(OKGREEN, self.msg, ENDC))

    def warning(self):
        print('{}{}{}'.format(WARNING, self.msg, ENDC))

    def fail(self):
        print('{}{}{}{}'.format(FAIL, BOLD, self.msg, ENDC))


#===============================FUNCTIONS=====================================

def has_valid_variables() -> bool:
    """Check validity of user-provided variables."""

    error_prompt = 'error: \'{}\' is not a valid {}'

    if not os.path.isdir(SUBFILES_DIR):
        ColorPrint(error_prompt.format(SUBFILES_DIR, 'directory')).fail()
        return False
    
    if VARS_FILE not in os.listdir(SUBFILES_DIR):
        ColorPrint(error_prompt.format(VARS_FILE, 'file')).fail()
        return False

    vars_path = os.path.join(SUBFILES_DIR, VARS_FILE)
    with open(vars_path, 'r') as f:
        vars_data = f.read()
    
    try:
        pattern = re.compile(r'(\w+)[\ =]+([^\ \n]+)')
        variables = {g[0]:g[1] for g in re.findall(pattern, vars_data)}
    except:
        ColorPrint('error reading variables file').fail()
        return False

    global DOWNLOADS, BADGES, SHEET, KEYFILE, AGENT

    DOWNLOADS = variables['DOWNLOADS_PATH']
    if not os.path.isdir(DOWNLOADS):
        ColorPrint(error_prompt.format(DOWNLOADS, 'directory')).fail()
        return False
    
    BADGES = variables['BADGES_PATH']
    if not os.path.isdir(BADGES):
        ColorPrint(error_prompt.format(BADGES, 'directory')).fail()
        return False

    KEYFILE = variables['JSON_KEY_FILE']
    if not os.path.isfile(KEYFILE):
        ColorPrint(error_prompt.format(KEYFILE, 'file')).fail()
        return False

    SHEET = variables['GOOGLE_SHEET_NAME']
    AGENT = variables['EMAIL']

    return True


def get_google_sheet_data():
    print('INFO - Connecting with google worksheets...')
    
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive'
        ]
    credentials = SAC.from_json_keyfile_name(KEYFILE, scope)
    client   = gspread.authorize(credentials)
    gsheet   = client.open(SHEET).sheet1
    df       = pd.DataFrame(gsheet.get_all_records())
    df.index = np.arange(2, len(df) + 2)

    print('INFO - Connection successful.\n')

    return gsheet, df


def set_up_logger():
    extra = {'image': None}
    cust_fmt = '%(asctime)s    %(image)12s    %(levelname)s: %(message)s'
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    root_logger.addHandler(stream_handler)

    log_path = os.path.join(SUBFILES_DIR, 'log')
    
    log_formatter = logging.Formatter(cust_fmt, '%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)

    root_logger.addHandler(file_handler)
    root_logger = logging.LoggerAdapter(root_logger, extra)
    

def sort_spreadsheet(wks):
    """Optional sort of google sheet"""

    prompt   = 'Ready to sort spreadsheet? (y/n)  '
    response = input(prompt)

    if response == 'y':
        by_city   = (8,'asc')
        by_county = (9,'asc')
        by_state  = (10,'asc')
        r = 'A2:J{}'.format(wks.row_count)

        wks.sort(by_state, by_county, by_city, range=r)
        print('INFO - Sorting complete.\n')


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

if __name__ == '__main__':
    args = parse_args()

    if not has_valid_variables():
        sys.exit(0)
    
    worksheet, df_raw = get_google_sheet_data()

    mode = [k for k,v in vars(args).items() if v == True][0]

    set_up_logger()

    p = Processor(mode, df_raw, worksheet)
    p.run_scanner()

#    if args.scan:
#        sort_spreadsheet(worksheet)