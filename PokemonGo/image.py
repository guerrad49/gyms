"""
PokemonGo.image
---------------

This module contains BadgeImage class for reading values from
a screenshot of a PokemonGo badge in PNG format. Phone model-
specific parameters are set in ModelParams class. These 
parameters help in extracting text from regions of an image 
by first preprocessing.
"""


import os
import re
from typing import Optional

import cv2
import numpy as np
import pytesseract

from .exceptions import UnsupportedPhoneModel, InputError


TOTAL_ACTIVITY_RE = re.compile(r"""
    (?P<victories>\d{1,4})           # Victories.
    [\n\ ]+
    ((?P<days>\d{1,3})d[\ ]?)?       # Days.
    ((?P<hours>\d{1,2})h[\ ]?)?      # Hours.
    ((?P<minutes>\d{1,2})m[\ ]?)?    # Minutes.
    ((\d{1,2})s)?                    # Seconds (very rare).
    [\n\ ]+
    (?P<treats>\d{1,4})              # Treats.
    """, re.X|re.S)

iSE_DIMENSIONS = (1334, 750)
i11_DIMENSIONS = (1792, 828)
i15_DIMENSIONS = (2556, 1179)


class ModelParams:
    """
    Class to store model dependent parameters for a BadgeImage.
    Cannot be used on unknown models.
    """

    def __init__(self, dimensions):
        if dimensions == iSE_DIMENSIONS:
            self.model      = 'iSE'
            self.scale      = 1.75
            self.titleStart = 50
            self.titleEnd   = 140
            self.activStart = 975
            self.activEnd   = 1100
        elif dimensions == i11_DIMENSIONS:
            self.model      = 'i11'
            self.scale      = 1.5
            self.titleStart = 60
            self.titleEnd   = 150
            self.activStart = 1075
            self.activEnd   = 1225
        elif dimensions == i15_DIMENSIONS:
            self.model      = 'i15'
            self.scale      = 1
            self.titleStart = 110
            self.titleEnd   = 210
            self.activStart = 1550
            self.activEnd   = 1800
        else:
            raise UnsupportedPhoneModel

        
class BadgeImage:
    """
    Class for processing a gym badge's image and extracting text.

    Examples
    --------
    >>> # Use relative path.
    >>> img = BadgeImage('badges/IMG_0001.PNG')
    """
    
    def __init__(
            self, 
            path: str, 
            verbose: Optional[bool] = False
            ) -> None:
        """
        Parameters
        ----------
        path:
            The file path to the image.
        verbose:
            Print progress statements.
        """

        self.path = path
        self.verbose = verbose
        if self.verbose:
            print('Scanning  {}'.format(path))
        self.image = cv2.imread(path)
        self.params = ModelParams(self.image.shape[:2])
        self.errors = list()


    def set_title_crop(
            self, 
            offset: Optional[int] = 0
            ) -> None:
        """
        Set the cropped image containing the badge title.

        Parameters
        ----------
        offset:
            The value to offset the title's vertical start.

        Exceptions
        ----------
        IndexError if offset value is too large.
        """

        titleNorth = self.params.titleStart - offset
        if titleNorth < 0:
            raise IndexError("Excessive offset value")
        
        self.titleCrop = self.image[
            titleNorth : self.params.titleEnd, 
            0 : self.image.shape[1]
            ]
    

    def soften_title_overlay(self) -> None:
        """
        Reconstruct title image by softening phone status from title 
        using inpainting.

        Exceptions
        ----------
        AttributeError if self.titleCrop is not initialized.
        TypeError if self.titleCrop is not <np.ndarray> type.

        See Also
        --------
        BadgeImage.set_title_crop
        """

        if not isinstance(self.titleCrop, np.ndarray):
            msg  = 'argument "{}" '.format(self.titleCrop)
            msg += 'must be <np.ndarray> type'
            raise TypeError(msg)
        
        # Reconstruct darkest pixels i.e. the status bar.
        lowerBound = np.array([0, 0, 0], dtype=np.uint8)
        upperBound = np.array([100, 100, 100], dtype=np.uint8)
        mask = cv2.inRange(self.titleCrop, lowerBound, upperBound)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.dilate(mask, kernel, iterations=1)

        self.titleCrop = cv2.inpaint(
            self.titleCrop, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA
            )
    

    def set_activity_crop(self) -> None:
        """
        Set the cropped image containing the badge activity section.
        """

        self.activityCrop = self.image[
            self.params.activStart : self.params.activEnd, 
            0 : self.image.shape[1]
            ]


    def get_activity_vals(
            self, 
            activityText: str
            ) -> dict:
        """
        Compute badge statistics from extracted activity text.

        Parameters
        ----------
        activityText:
            The extracted text from the activity section.
        
        Returns
        -------
        The dictionary containing badge statistics.

        Exceptions
        ----------
        InputError if regex search does not return match.

        See Also
        --------
        BadgeImage.get_text
        """

        match = re.search(TOTAL_ACTIVITY_RE, activityText)

        if match is None:
            self.errors.append('STATS')
            # Manually enter image stats.
            prompt = 'Enter STATS for `{}`:\t'.format(self.path)
            statsText = input(prompt).strip()
            # Try matching our regex string again.
            match  = re.search(TOTAL_ACTIVITY_RE, statsText)
            # If no match still, raise error.
            if match is None:
                raise InputError
        
        d = match.groupdict(default=0)
        return {k:int(v) for k,v in d.items()}
    

    def get_text(
            self, 
            region: str = 'all'
            ) -> str:
        """
        Retrieves all text from image region.

        Parameters
        ----------
        region:
            The image region ['all', 'title', 'activity'].
        
        Returns
        -------
        The extracted text string.

        Exceptions
        ----------
        AttributeError if region crop was not initialized.
        """

        if region == 'all':
            image = self.image
        elif region == 'title':
            image = self.titleCrop
        elif region == 'activity':
            image = self.activityCrop
        else:
            print("Invalid region value")
            return ''

        # Pre-processing.
        height = round(image.shape[0] * self.params.scale)
        width  = round(image.shape[1] * self.params.scale)
        resized   = cv2.resize(image, (width, height))
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(grayscale, 200, 230, cv2.THRESH_BINARY)

        txt = pytesseract.image_to_string(thresh, lang="eng")

        # Text cleanup.
        txt = txt.replace("’", "'")
        if region == 1:  # Title only.
            txt = txt.replace('\n', ' ')
        elif region == 2:  # Activity only.
            txt = txt.replace('O', '0')

        return txt.strip().lower()
        
    
    def to_storage(
            self, 
            directory: str, 
            newId: int
            ) -> None:
        """
        Move image file to storage with a new id.

        Parameters
        ----------
        directory:
            The path to storage directory.
        newId:
            The new base id used in renaming image.
        """
    
        newName = 'IMG_{:04d}.PNG'.format(newId)
        newPath = os.path.join(directory, newName)
        os.rename(self.path, newPath)
        self.path = newPath   # Update image location.

        if self.verbose:
            print('INFO - BadgeImage successfully relocated.')
