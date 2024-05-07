#!/usr/bin/env python3

import os
import sys
import argparse

from PokemonGo import utils
from PokemonGo import GoogleSheet, BadgeImage, GoldGym


#===============================FUNCTIONS=====================================
    
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

    utils.load_env()
    
    queue = utils.get_queue()
    if len(queue) == 0:
        sys.exit('---Processor ended---\n')

    gs = GoogleSheet(os.environ['KEY_PATH'], os.environ['SHEET_NAME'])

    nextId = gs.processed['image'].max() + 1
    ids = range(nextId, nextId + len(queue))

    print('\nINFO - Begin scanning process.\n')

    for id, path in zip(ids, queue):
        img = BadgeImage(path)
        imgData = img.get_title() | img.get_gym_activity()   # python3.9+

        titleFromDf, ridx = gs.find(imgData['title'], gs.unprocessed)
        imgData['title'] = titleFromDf

        coords = gs.unprocessed.at[ridx,'latlon']            

        gg = GoldGym(id, **imgData)
        gg.set_time_defended()
        gg.set_style()
        gg.set_address(coords, os.environ['EMAIL'])
        gg.set_city()
        gg.set_county()
        gg.set_state()

        gymRow = list(gg)
        img.to_storage(os.environ['BADGES'], id)

        gs.write_row(ridx, gymRow)
        print()

    gs.geo_sort()