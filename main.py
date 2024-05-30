#!/usr/bin/env python3

import pdb
import os
import sys
import argparse

from PokemonGo import (
    GymSheet, GymBadge, GoldGym, 
    utils
)


#===============================FUNCTIONS=====================================
    
# def parse_args():
#     command_desc = 'Scan badge data from PNG files.'
#     p = argparse.ArgumentParser(description=command_desc)

#     flags = p.add_mutually_exclusive_group()
#     flags.add_argument('-s', '--scan', action='store_true',
#         help='scan new badges')
#     flags.add_argument('-u', '--update', action='store_true',
#         help='update badge given')

#     args = p.parse_args()
            
#     return args


#==================================MAIN=======================================

if __name__ == '__main__':
    # args = parse_args()

    utils.load_env()
    utils.set_logger()
    
    queue = utils.get_queue()
    if len(queue) == 0:
        sys.exit('---Processor ended---\n')

    gs = GymSheet(os.environ['KEY_PATH'], os.environ['SHEET_NAME'])

    nextId = gs.processed['uid'].max() + 1
    ids = range(nextId, nextId + len(queue))

    print('\nINFO - Begin scanning process.\n')

    for id, path in zip(ids, queue):
        img = GymBadge(path)
        imgData  = {'title': img.get_title(), 'model': img.model}
        imgData |= img.get_gym_activity()   # python3.9+

        titleFromDf, ridx = gs.find(imgData['title'])
        imgData['title'] = titleFromDf

        coords = gs.unprocessed.at[ridx,'latlon']

        gym = GoldGym(id, **imgData)
        gym.set_time_defended()
        gym.set_style()
        gym.set_address(coords, os.environ['EMAIL'])
        gym.set_city()
        gym.set_county()
        gym.set_state()

        img.to_storage(os.environ['BADGES'], id)
 
        gs.write_row(ridx, gym)
        errors = gs.errors + img.errors + gym.errors
        utils.log_entry(id, errors)
        print()

    gs.geo_sort()