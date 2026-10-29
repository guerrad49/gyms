"""
This module provides helper functions for PokemonGo.sheet and main.py.
Aside from `are_similar`, all others are optional depending if the 
user decides to rewrite or use a new `main.py` script altogether.
"""


import os
import sys
import logging
import argparse
from difflib import SequenceMatcher

from dotenv import dotenv_values


SIMILARITY_MIN = 0.9   # 90 percent


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-u', '--updates', action='store_true', 
        help='process gym updates only')
    p.add_argument('-v', '--verbose', action='store_true', 
        help='print progress statements')
    return p.parse_args()


def are_similar(x: str, y: str) -> bool:
    """
    Determine if two texts are at least 90% similar.

    :param str x: The first text.
    :param str y: The second text.

    .. warning::
        The similarity percentage may be too high for short strings.
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
    """
    Check and load package environment variables.
    
    :raises EnvironmentError: if environment file not loaded.
    :raises FileNotFoundError: if json key file not found.
    """

    # Get top level directory for package.
    packageDir = os.path.dirname(__file__)
    topDir     = os.path.dirname(packageDir)

    requirements = os.path.join(topDir, 'requirements')

    # Load environment.
    envPath = os.path.join(requirements, 'variables.env')
    config = dotenv_values(envPath)
    if '' in config.values() or None in config.values():
        raise EnvironmentError
    
    # Check json key file exits.
    keyfile = os.path.join(requirements, config['JSON_KEY'])
    if not os.path.isfile(keyfile):
        raise FileNotFoundError
    
    os.environ['SHEET_NAME'] = config['SHEET_NAME']
    os.environ['EMAIL']      = config['EMAIL']
    os.environ['KEY_PATH']   = keyfile
    os.environ['LOGGER']     = os.path.join(requirements, config['LOG_FILE'])
    os.environ['DOWNLOADS']  = os.path.join(os.getenv('HOME'), 'Downloads')
    os.environ['BADGES']     = os.path.join(topDir, 'badges')


def get_queue(verbose: bool) -> list:
    """
    Build a queue of images to scan.
    
    :param bool verbose: If True, print progress statements.
    :returns: List of images to scan.
    """

    downloads = os.environ['DOWNLOADS']
    queue = [
        os.path.join(downloads, x) 
        for x in os.listdir(downloads) 
        if x.endswith('.PNG')
        ]

    qLen = len(queue)
    if verbose:
        print('INFO - Found {} image(s).'.format(qLen))
    if qLen == 0:
        sys.exit('---Processor ended---\n')
    
    return queue


def set_logger() -> None:
    """Set configurations for package logger."""
    
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        filename = os.environ['LOGGER'], 
        format   = '%(asctime)s   %(message)s', 
        datefmt  = '%Y-%m-%d %H:%M:%S', 
        )


def log_entry(gymId: int, errors: list) -> None:
    """
    Compose message body and create entry in log. The user should 
    have previously called `meth:set_logger`.

    :param int gymId: The unique id number identifying a gym.
    :param list errors: The list of errors detected in submodules.
    """

    logger = logging.getLogger(__name__)

    msg = 'ID: {:04}'.format(gymId)
    if errors:
        errStr = ', '.join(errors)
        msg += '   Errors: {}'.format(errStr)

    logger.warning(msg)
