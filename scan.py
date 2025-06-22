#!/usr/bin/env python3

import pdb
import os
import sys

from PokemonGo import (
    GymSheet, GymBadge, GoldGym, 
    utils
)


if __name__ == '__main__':
    args = utils.parse_args()

    utils.load_env()
    utils.set_logger()
    
    queue = utils.get_queue()
    if len(queue) == 0:
        sys.exit('---Processor ended---\n')

    gs = GymSheet(os.environ['KEY_PATH'], os.environ['SHEET_NAME'])

    # Consider finding nextId within while loop.
    if not args.updates:
        nextId = gs.processed['uid'].max() + 1
        ids = list(range(nextId, nextId + len(queue)))

    print('\nINFO - Begin scanning process.\n')

    for i,path in enumerate(queue):
        img = GymBadge(path)
        imgData  = {'title': img.get_title(), 'model': img.model}
        imgData |= img.get_gym_activity()   # python3.9+

        # new gym
        if not args.updates:
            titleFromDf, ridx = gs.find(imgData['title'], True)
            coords = gs.unprocessed.at[ridx, 'latlon']
            id = ids.pop(0)
        else:  # update old gym
            titleFromDf, ridx = gs.find(imgData['title'], False)
            coords = gs.processed.at[ridx, 'latlon']
            id = gs.processed.at[ridx, 'uid']
        
        imgData['title'] = titleFromDf

        gym = GoldGym(id, **imgData)
        gym.set_time_defended()
        gym.set_style()
        
        # fields needed for new gyms
        if not args.updates:
            gym.set_address(coords, os.environ['EMAIL'])
            gym.set_city()
            gym.set_county()
            gym.set_state()

        # pdb.set_trace()

        img.to_storage(os.environ['BADGES'], id)
 
        gs.write_row(ridx, gym)
        errors = gs.errors + img.errors + gym.errors
        utils.log_entry(id, errors)
        print()

    gs.geo_sort()