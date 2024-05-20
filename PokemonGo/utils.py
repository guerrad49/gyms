import os
import logging
from difflib import SequenceMatcher

from dotenv import dotenv_values

from .exceptions import InvalidEnvironment


SIMILARITY_MIN = 0.9


def are_similar(x: str, y: str) -> bool:
    """
    Determine if string similarity is above a threshold.
    WARNING: For short strings, user may want to decrease SIMILARITY_MIN.
    """

    likeness = SequenceMatcher(None, x, y).ratio()

    if likeness >= SIMILARITY_MIN:
        prompt = 'Found similar match \'{}\'. Accept? (y/n)   '.format(x)
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
    os.environ['EMAIL']      = config['EMAIL']
    os.environ['KEY_PATH']   = keyfile
    os.environ['LOGGER']     = os.path.join(subfiles, config['LOG_FILE'])
    os.environ['DOWNLOADS']  = os.path.join(os.getenv('HOME'), 'Downloads')
    os.environ['BADGES']     = os.path.join(topDir, 'badges')


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
        msg  = 'INFO - Found the following images:\n'
        msg += '\n'.join(queue)
        msg += '\n'
        print(msg)
    
    return queue


def set_logger() -> None:
    """Set configurations for package logger."""
    
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        filename = os.environ['LOGGER'], 
        format   = '%(asctime)s   %(message)s', 
        datefmt  = '%Y-%m-%d %H:%M:%S', 
        )


def log_entry(gymUid: int, errors: list) -> None:
    """
    Compose message body and create entry in log.

    Parameters
    ----------
    gymUid:
        The unique id number identifying a gym
    errors:
        The list of errors i.e. CITY, TITLE, STATS, etc
    
    See Also
    --------
    utils.set_logger
    """

    logger = logging.getLogger(__name__)

    msg = 'ID: {:04}'.format(gymUid)
    if errors:
        errStr = ', '.join(errors)
        msg += '   Errors: {}'.format(errStr)

    logger.warning(msg)
