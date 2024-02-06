#!/usr/bin/env python3

import os
import re
import multiprocessing as mp

import pandas as pd

import pytesseract                     # packages for reading
from PIL import Image, ImageEnhance    # and enhancing images


BADGES = '/Users/david_guerra/Documents/Programming/python/gyms/badges'

DEF_COORDS = (300,1080,520,1220)
DEF_PAT = re.compile(r"""
.+DEFENDED\n                    # values start after DEFENDED and newline
((?P<days>\d{1,3})d[\ ]?)?      # days defended
((?P<hrs>\d{1,2})h[\ ]?)?       # hours defended
((?P<mins>\d{1,2})m[\ ]?)?      # minutes defended
((?P<secs>\d{1,2})s)?           # seconds defended
\n""", re.X)

DEF_THRESH = 161

#====================================================================

def set_time_defended(_id, fname, check):
    errors = {'id':_id, 'read':False, 'match':False}

    with Image.open(fname) as img:
        def_img      = img.crop(DEF_COORDS)
        contrast_img = ImageEnhance.Contrast(def_img).enhance(2)
        gray_img     = contrast_img.convert(mode='L')
        final_img    = gray_img.point(lambda x: 255 if x > DEF_THRESH else 0)
        txt          = pytesseract.image_to_string(final_img)

    try:
        stats = re.search(DEF_PAT, txt).groupdict()
    except AttributeError:
        errors['read'] = True
    else:
        for key,val in stats.items():
            if val in [None, 'O']:
                stats[key] = 0
            else:
                stats[key] = int(val)

        total = stats['days'] + stats['hrs']/24 + stats['mins']/1440 \
            + stats['secs']/86400

        if total != check:
            errors['match'] = True
        
    return errors

def prep_values(row):
    _id = row[1]['image']
    full_path = os.path.join(BADGES, 'IMG_{:04d}.PNG'.format(_id))
    victories = row[1]['victories']
    
    return _id, full_path, victories

#====================================================================

if __name__ == '__main__':
    df_raw = pd.read_csv('data_new.csv', index_col=0)
    df = df_raw.astype({'image':'uint16', 'victories':'uint16'})
    chunk = df.shape[0] * 2

    num_cpus = mp.cpu_count()

    with mp.Pool(num_cpus) as pool:
        arg_pairs = pool.imap(prep_values, df.iterrows(), chunksize=chunk)
        errors = [pool.apply(set_time_defended, args=tup) for tup in arg_pairs]

    df_errors = pd.DataFrame(data=errors)
    df_narrow = df_errors[(df_errors['read']) | (df_errors['match'])]
    print(df_narrow)
