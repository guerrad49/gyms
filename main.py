#!/usr/bin/env python3

import os
import sys
import argparse

from PokemonGo import utils
from PokemonGo import GoogleSheet, Image, Gym


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
    gs.retrieve_data()

    next_id = gs.processed['image'].max() + 1
    ids = range(next_id, next_id + len(queue))

    print('\nINFO - Begin scanning process.\n')

    for id, path in zip(ids, queue):
        img = Image(path)
        img_data = img.get_title() | img.get_stats()   # python3.9+

        title_from_df, ridx = gs.find(img_data['title'], gs.unprocessed)
        img_data['title'] = title_from_df

        coords = gs.unprocessed.at[ridx,'coordinates']            

        g = Gym(id)
        g.set_fields_from_image(img_data)
        g.set_location_fields(coords, os.environ['EMAIL'])

        gym_row = g.format_fields()
        img.to_storage(os.environ['BADGES'], id)

        gs.write_row(ridx, gym_row)
        print()

    gs.sort_by_location()