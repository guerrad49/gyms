import os
import re

import cv2
import numpy as np
import pytesseract

from .exceptions import UnsupportedPhoneModel, InputError


iSE_DIMENSIONS = (1334, 750)
i11_DIMENSIONS = (1792, 828)
i15_DIMENSIONS = (2556, 1179)

IMG_STATS_RE = re.compile(r"""
        (?P<victories>\d{1,4})           # victories
        [\n\ ]+
        ((?P<days>\d{1,3})d[\ ]?)?       # days
        ((?P<hours>\d{1,2})h[\ ]?)?      # hours
        ((?P<minutes>\d{1,2})m[\ ]?)?    # minutes
        ((\d{1,2})s)?                    # seconds (very rare)
        [\n\ ]+
        (?P<treats>\d{1,4})              # treats
        """, re.X|re.S)


class Image:
    '''A class for text-reading a PNG image'''
    
    def __init__(self, path: str):
        '''
        Parameters
        ----------
        path:
            The file path to the image
        '''

        self.path  = path
        self.image = cv2.imread(path)
        self.set_processing_params()

    
    def set_processing_params(self):
        '''
        Determine iPhone model parameters from image dimensions.
        Cannot be used on unknown models.
        '''

        dimensions = self.image.shape[:2]
        
        if dimensions == iSE_DIMENSIONS:
            self.scale = 1.75
            self.title_start = 50
            self.title_end   = 140
            self.stats_start = 975
            self.stats_end   = 1100
        elif dimensions == i11_DIMENSIONS:
            self.scale = 1.5
            self.title_start = 60
            self.title_end   = 150
            self.stats_start = 1075
            self.stats_end   = 1225
        elif dimensions == i15_DIMENSIONS:
            self.scale = 1
            self.title_start = 110
            self.title_end   = 210
            self.stats_start = 1550
            self.stats_end   = 1800
        else:
            raise UnsupportedPhoneModel


    def get_text(self, image: np.ndarray = None) -> str:
        '''
        Parameters
        ----------
        image: 
            The array representing an image

        Returns
        -------
            The text string for entire image
        '''

        if image is None:
            image = self.image

        # pre-processing        
        height = round(image.shape[0] * self.scale)
        width  = round(image.shape[1] * self.scale)
        resized   = cv2.resize(image, (width, height))
        grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(grayscale, 200, 230, cv2.THRESH_BINARY)

        return pytesseract.image_to_string(thresh)


    def get_title(self) -> dict:
        '''
        Extract image title from predetermined crop
        
        Returns
        -------
        The dict containing the title for badge image
        '''

        cropped = self.image[
            self.title_start:self.title_end, 
            0:self.image.shape[1]
            ]
        text = self.get_text(cropped)
        text = text.replace("’", "'")   # proactive error handling
        text = text.replace('\n', ' ')

        return {'title': text.strip().lower()}


    def get_stats(self) -> dict:
        '''
        Extract image stats from predetermined crop
        
        Returns
        -------
        The dict containing the stats for badge image
        '''

        cropped = self.image[
            self.stats_start:self.stats_end, 
            0:self.image.shape[1]
            ]
        txt = self.get_text(cropped)
        txt = txt.replace('O', '0')   # proactive error handling

        match = re.search(IMG_STATS_RE, txt)
        if match is None:
            # manually enter image stats
            prompt  = 'Enter STATS for `{}`:\t'.format(self.path)
            new_txt = input(prompt).strip()
            match   = re.search(IMG_STATS_RE, new_txt)
            if match is None:
                raise InputError
        
        return match.groupdict()
        
    
    def to_storage(self, directory: str, new_id: int):
        """
        Move image file to storage with a new id.

        Parameters
        ----------
        directory:
            The path to storage directory
        new_id:
            The new base id used in renaming image
        """
    
        new_name = 'IMG_{:04d}.PNG'.format(new_id)
        new_path = os.path.join(directory, new_name)
        os.rename(self.path, new_path)
        self.path = new_path   # update image location

        print('INFO - Image successfully relocated.')
