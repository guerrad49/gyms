import unittest
import unittest.mock

import pytest

from PokemonGo.image import BadgeImage
from PokemonGo.exceptions import UnsupportedPhoneModel


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.im01 = BadgeImage('tests/images/IMG_0001.PNG')
        self.im02 = BadgeImage('tests/images/IMG_1000.PNG')
        self.im03 = BadgeImage('tests/images/IMG_1190.PNG')

    #==========================================================================
    def test_empty_instance(self):
        self.assertRaises(TypeError, BadgeImage)

    #==========================================================================
    def test_image_ise(self):
        self.assertEqual(self.im01.scale, 1.75)

    def test_image_i11(self):
        self.assertEqual(self.im02.scale, 1.5)

    def test_image_i15(self):
        self.assertEqual(self.im03.scale, 1)

    def test_image_unsupported(self):
        path = 'tests/images/SHAKA.PNG'
        self.assertRaises(UnsupportedPhoneModel, BadgeImage, path)

    #==========================================================================
    def test_title(self):
        self.assertEqual(self.im01.get_title(), 'third ward park playground')

    #==========================================================================
    def test_stats(self):
        self.assertEqual(
            self.im02.get_gym_activity(), 
            {'victories':18, 'days':25, 'hours':18, 'minutes':1, 'treats':9}
            )

    def test_stats_manual(self):
        unittest.mock.builtins.input = lambda _: ""
        pass

if __name__ == '__main__':
    unittest.main()