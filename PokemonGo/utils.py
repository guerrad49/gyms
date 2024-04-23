import os
from difflib import SequenceMatcher

from dotenv import load_dotenv    # load env vars

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
    subfiles = os.path.join(os.environ['APP'], 'subfiles')

    # load environment
    env_path = os.path.join(subfiles, 'variables.env')
    if not load_dotenv(env_path):
        raise InvalidEnvironment
    
    # check json key file exits
    keyfile = os.path.join(subfiles, os.getenv('JSON_KEY'))
    if not os.path.isfile(keyfile):
        raise FileNotFoundError
    
    if not os.getenv('SHEET_NAME'):
        raise InvalidEnvironment
    
    if not os.getenv('EMAIL'):
        raise InvalidEnvironment
    
    os.environ['KEY_PATH'] = keyfile
    os.environ['DOWNLOADS'] = os.path.join(os.getenv('HOME'), 'Downloads')
    os.environ['BADGES'] = os.path.join(os.environ['APP'], 'badges')


def get_queue() -> list:
    """Returns True when successfully populated a queue to scan"""

    downloads = os.environ['DOWNLOADS']
    queue = [
        os.path.join(downloads, x) for x in os.listdir(downloads) \
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