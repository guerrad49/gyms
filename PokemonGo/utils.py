import os
import logging
from typing import Optional
from difflib import SequenceMatcher

from dotenv import dotenv_values

from .exceptions import InvalidEnvironment


SIMILARITY_MIN = 0.9
LOG_PATH = 'subfiles/pogo.log'


def are_similar(x: str, y: str) -> bool:
    """
    Determine if string similarity is above a threshold.
    WARNING: For short strings, user may want to decrease SIMILARITY_MIN.
    """

    likeness = SequenceMatcher(None, x, y).ratio()

    if likeness >= SIMILARITY_MIN:
        prompt = 'Found similar match \'{}\'. Accept? (y/n)\t'.format(x)
        if input(prompt) == 'y':
            return True
        else:
            return False

    return False


def load_env() -> None:
    """Check and load package environment variables."""

    # get top level directory for package
    packageDir = os.path.dirname(__file__)
    topDir     = os.path.dirname(packageDir)

    subfiles = os.path.join(topDir, 'subfiles')

    # load environment
    envPath = os.path.join(subfiles, 'variables.env')
    config = dotenv_values(envPath)
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
    os.environ['BADGES'] = os.path.join(topDir, 'badges')


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


def set_logger() -> None:
    """Set configurations for package logger."""
    
    pogoFormat = '%(asctime)s   %(levelname)6s: %(image)s   %(message)s'
    logger = logging.getLogger('pogoLog')
    logging.basicConfig(
        filename = LOG_PATH, 
        format   = pogoFormat, 
        datefmt  = '%Y-%m-%d %H:%M:%S', 
        level    = logging.DEBUG
        )


def log_error(type: str, gymUid: int, details: Optional[str] = '') -> None:
    """
    Helper function for logging errors within modules.

    Parameters
    ----------
    type:
        The type of error i.e. CITY, TITLE, STATS, etc
    gymUid:
        The unique id number identifying a gym
    details:
        Extra details to include when logging error
    """

    logger = logging.getLogger('pogoLog')

    if details:
        msg = '{} error - {}'.format(type.upper(), details)
    else:
        msg = '{} error'.format(type.upper())

    imgName = '{:04}'.format(gymUid)
    logger.debug(msg, extra={'image': imgName})
