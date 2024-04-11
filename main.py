#!/usr/bin/env python3

import os
import sys
import argparse

from dotenv import load_dotenv    # load env vars

from PokemonGo import GoogleSheet, Image, Gym, ColorPrint


#=============================GLOBAL VARIABLES================================

DOWNLOADS = os.path.join(os.getenv('HOME'), 'Downloads')
BADGES    = os.path.join(os.path.dirname(__file__), 'badges')


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

def get_queue() -> list:
    """Returns True when successfully populated a queue to scan"""

    queue = [
        os.path.join(DOWNLOADS, x) for x in os.listdir(DOWNLOADS) \
        if x.endswith('.PNG')
        ]

    if len(queue) == 0:
        print('INFO - No images found.\n')
    else:
        prompt  = 'INFO - Found the following images:\n'
        prompt += '\n'.join(queue)
        prompt += '\n'
        print(prompt)
    
    return queue
    
    
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

    if not has_valid_environment():
        sys.exit(0)
    
    queue = get_queue()
    if len(queue) == 0:
        ColorPrint('---Processor ended---\n').fail()
        sys.exit(0)

    gs = GoogleSheet()
    gs.split()
    next_id = gs.scanned['image'].max() + 1
    ids = range(next_id, next_id + len(queue))

    ColorPrint('\nINFO - Begin scanning process.\n').proc()

    for id, path in zip(ids, queue):
        img_data = dict()
        img = Image(path)
        img_data['title'] = img.get_title_txt()
        stats = img.get_stats_info()
        img_data.update(stats)

        ridx, title_from_df = gs.find(path, img_data['title'])

        coords = gs.df.at[ridx,'coordinates']
        if title_from_df != "":
            img_data['title'] = title_from_df
        g = Gym(id, img_data, coords)
        gym_row = g.format_vars()

        img.to_storage(BADGES, id)
        gs.write_row(ridx, gym_row)
        print()

    gs.sort_by_location()