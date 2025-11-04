#!/usr/bin/env python3

import pdb
import os

from PokemonGo import (
    GymSheet, BadgeImage, GoldGym, 
    utils
)


if __name__ == '__main__':
    args = utils.parse_args()

    utils.load_env()
    utils.set_logger()
    
    queue = utils.get_queue(args.verbose)

    gs = GymSheet(
        os.environ['KEY_PATH'], 
        os.environ['SHEET_NAME'], 
        args.verbose
        )

    # Generate list of unique ids to assign images.
    if not args.updates:
        nextId = gs.processed['uid'].max() + 1
        ids = list(range(nextId, nextId + len(queue)))

    if args.verbose:
        print('\nINFO - Begin scanning process.\n')

    # Begin scanning process.
    for i,path in enumerate(queue):
        img = BadgeImage(path, args.verbose)

        # ========== Begin title extract ==========
        # Single line titles (most cases).
        img.set_title_crop()
        titleTxt = img.get_text(region='title')
        titleFound, rowIndex = gs.find(titleTxt)

        # Two line titles.
        if rowIndex == -1:
            img.set_title_crop(offset=40)
            img.soften_title_overlay()
            titleTxt = img.get_text(region='title')
            titleFound, rowIndex = gs.find(titleTxt)

            # Multi-line titles require user input for now.
            if rowIndex == -1:
                titleFound, rowIndex = gs.find_from_input()

        # ========== End title extract ==========

        # New gym.
        if not args.updates:
            coords = gs.unprocessed.at[rowIndex, 'latlon']
            id = ids.pop(0)
        else:  # Update old gym.
            coords = gs.processed.at[rowIndex, 'latlon']
            id = gs.processed.at[rowIndex, 'uid']

        # Initialize data that will be passed to google sheet.
        rowDict = {
            'uid': id, 
            'title': titleFound, 
            'model': img.params.model
            }
        
        # Extract all activity data from badge image.
        img.set_activity_crop()
        activityTxt = img.get_text(region='activity')
        gymActivity = img.get_activity_vals(activityTxt)

        # Initialize gym with extracted data.
        gym = GoldGym(title=titleFound, **gymActivity)
        gym.set_time_defended()
        gym.set_style()
        
        # Obtain location fields for new gyms.
        if not args.updates:
            gym.set_address(coords, os.environ['EMAIL'])
            gym.set_city()
            gym.set_county()
            gym.set_state()

        rowDict |= vars(gym)   # python3.9+
        del rowDict['address']
        del rowDict['errors']

        # Write data to spreadsheet.
        gs.write_row(rowIndex, rowDict)

        # Log any/all errors.
        errors = gs.errors + img.errors + gym.errors
        utils.log_entry(id, errors)

        # Move image to storage once everything else succeeded.
        img.to_storage(os.environ['BADGES'], id)
        print()

    gs.geo_sort()