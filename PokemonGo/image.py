"""
PokemonGo.image
---------------

This module contains BadgeImage class for reading values from
a PokemonGo image badge in PNG format. Preprocessing with
optimal values depending on iPhone models are implemented prior
to text extraction.
"""


import os
import re

import cv2
import numpy as np
import pytesseract

from typing import Optional

from .exceptions import UnsupportedPhoneModel, InputError


iSE_DIMENSIONS = (1334, 750)
i11_DIMENSIONS = (1792, 828)
i15_DIMENSIONS = (2556, 1179)

TOTAL_ACTIVITY_RE = re.compile(r"""
    (?P<victories>\d{1,4})           # victories
    [\n\ ]+
    ((?P<days>\d{1,3})d[\ ]?)?       # days
    ((?P<hours>\d{1,2})h[\ ]?)?      # hours
    ((?P<minutes>\d{1,2})m[\ ]?)?    # minutes
    ((\d{1,2})s)?                    # seconds (very rare)
    [\n\ ]+
    (?P<treats>\d{1,4})              # treats
    """, re.X|re.S)


class BadgeImage:
    """
    An instance of this class used for extracting text from
    an image.

    Examples
    --------
    Requires valid relative or full path.
    >>> img = BadgeImage('/badges/IMG_0001.PNG')
    """
    
    def __init__(self, path: str) -> None:
        """
        Parameters
        ----------
        path:
            The file path to the image
        """

        self.path  = path
        self.image = cv2.imread(path)
        self.set_processing_params()

    
    def set_processing_params(self) -> None:
        """
        Determine iPhone model parameters from image dimensions.
        Cannot be used on unknown models.
        """

        dimensions = self.image.shape[:2]
        
        if dimensions == iSE_DIMENSIONS:
            self.scale      = 1.75
            self.titleStart = 50
            self.titleEnd   = 140
            self.activStart = 975
            self.activEnd   = 1100
        elif dimensions == i11_DIMENSIONS:
            self.scale      = 1.5
            self.titleStart = 60
            self.titleEnd   = 150
            self.activStart = 1075
            self.activEnd   = 1225
        elif dimensions == i15_DIMENSIONS:
            self.scale      = 1
            self.titleStart = 110
            self.titleEnd   = 210
            self.activStart = 1550
            self.activEnd   = 1800
        else:
            raise UnsupportedPhoneModel


    def get_title(self) -> str:
        """
        Extract badge title from image. Crops the portion containing
        the badge title.
        
        Returns
        -------
        The title text string

        See Also
        --------
        BadgeImage.get_text
        """

        titleCrop = self.image[
            self.titleStart : self.titleEnd,   #  top : bottom
            0 : self.image.shape[1]            # left : right
            ]
        text = self.get_text(titleCrop)
        text = text.replace("’", "'")   # proactive error handling
        text = text.replace('\n', ' ')

        return text.strip().lower()


    def get_gym_activity(self) -> dict:
        """
        Extract badge stats from image. Crops the portion containing
        the badge statistics under:
            VICTORIES | TIME DEFENDED | TREATS
        
        Returns
        -------
        The dictionary containing badge statistics

        See Also
        --------
        BadgeImage.get_text
        """

        activityCrop = self.image[
            self.activStart : self.activEnd,   #  top : bottom
            0 : self.image.shape[1]            # left : right
            ]
        text = self.get_text(activityCrop)
        text = text.replace('O', '0')   # proactive error handling

        match = re.search(TOTAL_ACTIVITY_RE, text)
        if match is None:
            # manually enter image stats
            # TODO: log the error
            prompt = 'Enter STATS for `{}`:\t'.format(self.path)
            inText = input(prompt).strip()
            match  = re.search(TOTAL_ACTIVITY_RE, inText)
            if match is None:
                raise InputError
        
        d = match.groupdict()
        return {k:int(v) for k,v in d.items()}
    

    def get_text(
            self, 
            image: Optional[np.ndarray] = None
            ) -> str:
        """
        Retrieves all text from an image array. If optional parameter
        isn't set, default is self.image attribute.

        Parameters
        ----------
        image: 
            The array representing an image

        Returns
        -------
            The text string for entire image

        See Also
        --------
        BadgeImage.get_title
        BadgeImage.get_gym_activity
        """

        if image is None:
            image = self.image

        # pre-processing        
        height = round(image.shape[0] * self.scale)
        width  = round(image.shape[1] * self.scale)
        resized   = cv2.resize(image, (width, height))
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(grayscale, 200, 230, cv2.THRESH_BINARY)

        return pytesseract.image_to_string(thresh)
        
    
    def to_storage(self, directory: str, new_id: int) -> None:
        """
        Move image file to storage with a new id.

        Parameters
        ----------
        directory:
            The path to storage directory
        new_id:
            The new base id used in renaming image
        """
    
        newName = 'IMG_{:04d}.PNG'.format(new_id)
        newPath = os.path.join(directory, newName)
        os.rename(self.path, newPath)
        self.path = newPath   # update image location

        print('INFO - BadgeImage successfully relocated.')
