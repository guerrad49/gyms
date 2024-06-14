#!/usr/bin/env python3

import pdb
import os
import sys

from PokemonGo import (
    GymSheet, GymBadge, GoldGym, 
    utils, exceptions
)


if __name__ == '__main__':
    utils.load_env()
    utils.set_logger()
    
    queue = utils.get_queue()
    if len(queue) == 0:
        sys.exit('---Processor ended---\n')

    gs = GymSheet(os.environ['KEY_PATH'], os.environ['SHEET_NAME'])

    nextId = gs.processed['uid'].max() + 1
    ids = list(range(nextId, nextId + len(queue)))

    print('\nINFO - Begin scanning process.\n')

    while ids:
    # for id, path in zip(ids, queue):
        path = queue.pop(0)
        img = GymBadge(path)
        imgData  = {'title': img.get_title(), 'model': img.model}
        imgData |= img.get_gym_activity()   # python3.9+

        try:
            # new gym
            titleFromDf, ridx = gs.find(imgData['title'], True)
            coords = gs.unprocessed.at[ridx, 'latlon']
            id = ids.pop(-1)
        except exceptions.TitleNotFound:
            # update old gym
            titleFromDf, ridx = gs.find(imgData['title'], False)
            coords = gs.processed.at[ridx, 'latlon']
            id = gs.processed.at[ridx, 'uid']
            ids.pop()
        
        imgData['title'] = titleFromDf

        gym = GoldGym(id, **imgData)
        gym.set_time_defended()
        gym.set_style()
        gym.set_address(coords, os.environ['EMAIL'])
        gym.set_city()
        gym.set_county()
        gym.set_state()

        pdb.set_trace()

    #     img.to_storage(os.environ['BADGES'], id)
 
    #     gs.write_row(ridx, gym)
    #     errors = gs.errors + img.errors + gym.errors
    #     utils.log_entry(id, errors)
    #     print()

    # gs.geo_sort()