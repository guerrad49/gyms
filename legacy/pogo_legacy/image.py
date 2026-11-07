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
    Class for processing a badge image and extracting relevant text. 

    :param str path: The file path to the image.
    :param bool verbose: (optional) If True, print progress statements.

    Examples: 

    .. code:: python

        >>> # Use relative path.
        >>> img = BadgeImage('badges/IMG_0001.PNG')
    """
    
    def __init__(
            self, 
            path: str, 
            verbose: Optional[bool] = False
            ) -> None:

        self.path = path
        self.verbose = verbose
        if self.verbose:
            print('Scanning  {}'.format(path))
        self.image = cv2.imread(path)
        self.params = ModelParams(self.image.shape[:2])
        self.errors = list()


    def set_title_crop(
            self, 
            northOffset: Optional[int] = 0
            ) -> None:
        """
        Crop full image to title region and set result to 
        :attr:`BadgeImage.titleCrop`.

        :param int northOffset: (optional) Offset title by given amount. 
            Positive value expands north.

        :raises IndexError: if `northOffset` exceeds image north.
        """

        titleNorth = self.params.titleStart - northOffset
        if titleNorth < 0:
            raise IndexError("Excessive northOffset value")
        
        self.titleCrop = self.image[
            titleNorth : self.params.titleEnd, 
            0 : self.image.shape[1]
            ]
    

    def soften_title_overlay(self) -> None:
        """
        Reconstruct title image by softening phone status from title 
        using inpainting. The resulting :attr:`BadgeImage.titleCrop` 
        typically yields better quality for reading text. Users should 
        make prior call to :meth:`BadgeImage.set_title_crop`.

        :raises AttributeError: if :attr:`BadgeImage.titleCrop` is not set.
        :raises TypeError: if :attr:`BadgeImage.titleCrop` is not 
            :class:`numpy.ndarray` type.

        .. seealso::
            https://docs.opencv.org/3.4/df/d3d/tutorial_py_inpainting.html
        """

        if not isinstance(self.titleCrop, np.ndarray):
            msg  = 'argument "{}" '.format(self.titleCrop)
            msg += 'must be <numpy.ndarray> type'
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
        Crop full image to activity region and set result to 
        :attr:`BadgeImage.activityCrop`.
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
        Compute badge statistics from extracted activity text. Users would 
        typically set `activityText` to the output of 
        :meth:`BadgeImage.get_text`.

        :param str activityText: The text to parse badge statistics.
        :returns: A dictionary containing badge statistics.
        :raises InputError: if regex search does not return match.
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
        Retrieves all text from specified image region. Preprocessing 
        is done using 
        `OpenCV <https://docs.opencv.org/3.4/d1/dfb/intro.html>`__ 
        before extracting text with :meth:`pytesseract.image_to_string`.

        :param str region: The image region. 
            Allowed values are ``all``, ``title``, ``activity``.
        :returns: The extracted text string in full lowercase.
        :raises AttributeError: if region crop was not initialized.
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
        Move image file to storage as `IMG_####.PNG` where the file 
        is assigned the `newId` value.

        :param str directory: The path to storage directory.
        :param int newId: The id used in renaming an image.
        """
    
        newName = 'IMG_{:04d}.PNG'.format(newId)
        newPath = os.path.join(directory, newName)
        os.rename(self.path, newPath)
        self.path = newPath   # Update image location.

        if self.verbose:
            print('INFO - BadgeImage successfully relocated.')
