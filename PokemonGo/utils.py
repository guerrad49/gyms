import os
from difflib import SequenceMatcher

from dotenv import dotenv_values

from .exceptions import InvalidEnvironment


SIMILARITY_MIN = 0.9


def are_similar(x: str, y: str) -> bool:
    '''
    Determine if string similarity is above a threshold.
    WARNING: For short strings, user may want to decrease SIMILARITY_MIN.
    '''

    likeness = SequenceMatcher(None, x, y).ratio()

    if likeness >= SIMILARITY_MIN:
        prompt = 'Found similar match \'{}\'. Accept? (y/n)\t'.format(x)
        if input(prompt) == 'y':
            return True
        else:
            return False

    return False


def load_env():
    # get top level directory for package
    pkg_dir = os.path.dirname(__file__)
    top_dir = os.path.dirname(pkg_dir)

    subfiles = os.path.join(top_dir, 'subfiles')

    # load environment
    env_path = os.path.join(subfiles, 'variables.env')
    config = dotenv_values(env_path)
    if '' in config.values() or None in config.values():
        raise InvalidEnvironment
    
    # check json key file exits
    keyfile = os.path.join(subfiles, config['JSON_KEY'])
    if not os.path.isfile(keyfile):
        raise FileNotFoundError
    
    os.environ['SHEET_NAME'] = config['SHEET_NAME']
    os.environ['EMAIL'] = config['EMAIL']
    os.environ['KEY_PATH'] = keyfile
    os.environ['DOWNLOADS'] = os.path.join(os.getenv('HOME'), 'Downloads')
    os.environ['BADGES'] = os.path.join(top_dir, 'badges')


def get_queue() -> list:
    """Returns True when successfully populated a queue to scan"""

    downloads = os.environ['DOWNLOADS']
    queue = [
        os.path.join(downloads, x) 
        for x in os.listdir(downloads) 
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