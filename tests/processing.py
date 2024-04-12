import os
import cv2
import pdb
import pytesseract
import re
import pandas as pd
import numpy as np
import multiprocessing as mp


PATTERN = re.compile(r"""
    .+TREATS
    [\n\ ]+
    (?P<victories>\d{1,4})           # victories
    [\n\ ]+
    ((?P<days>\d{1,3})d[\ ]?)?       # days defended
    ((?P<hours>\d{1,2})h[\ ]?)?      # hours defended
    ((?P<minutes>\d{1,2})m[\ ]?)?    # minutes defended
    ((\d{1,2})s)?                    # seconds defended (very rare)
    [\n\ ]+
    (?P<treats>\d{1,4})              # treats
    """, re.X|re.S)

BADGES = '/Users/david_guerra/Documents/Programming/python/gyms/main/badges'

#====================================================================

def pre_process(name, scale):
    image = cv2.imread(name)
    # crop = image[975:1100, 0:750]  # stats
    crop = image[50:140, 0:750]  # titles
    new_size = (round(750*scale), round(90*scale))
    stretch = cv2.resize(crop, new_size)
    gray = cv2.cvtColor(stretch, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 230, cv2.THRESH_BINARY)
    return pytesseract.image_to_string(thresh)

def has_stats(text):
    match = re.search(PATTERN, text)

    if match == None:
        text = text.replace('O','0')
        match = re.search(PATTERN, text)
        if match == None:
            return False
    return True

def has_matching_title(true, test):
    clean = test.replace('\n',' ')
    clean = clean.strip().lower()
    clean = clean.replace("’","'")
    if true == clean:
        return True
    return False

#====================================================================

if __name__ == '__main__':
    # gather truth values (one time)
    df = pd.read_csv('tests/data.csv', index_col=0)
    srs = df['title']
    srs = srs[:848]
    srs.index += 1

    # gather badge filenames (one time)
    files = [f for f in os.listdir(BADGES) if f.endswith('PNG')]
    files = sorted(files)[:848]
    files = [os.path.join(BADGES, f) for f in files]
    files.remove('IMG_0486.PNG')  # diff size
    files.remove('IMG_0596.PNG')  # diff size

    # will hold results
    results = pd.DataFrame()

    chunk = len(files) * 2
    num_cpus = mp.cpu_count()

    with mp.Pool(num_cpus) as pool:
        arg_pairs = pool.imap(pre_process, srs, chunksize=chunk)




# cv2.imshow('img', image)
# cv2.waitKey(0)