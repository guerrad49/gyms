import unittest
import unittest.mock

import pytest

from PokemonGo.image import GymBadge
from PokemonGo.exceptions import UnsupportedPhoneModel


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.im01 = GymBadge('tests/images/IMG_0001.PNG')
        self.im02 = GymBadge('tests/images/IMG_1000.PNG')
        self.im03 = GymBadge('tests/images/IMG_1190.PNG')

    #==========================================================================
    def test_empty_instance(self):
        self.assertRaises(TypeError, GymBadge)

    #==========================================================================
    def test_image_ise(self):
        self.assertEqual(self.im01.scale, 1.75)

    def test_image_i11(self):
        self.assertEqual(self.im02.scale, 1.5)

    def test_image_i15(self):
        self.assertEqual(self.im03.scale, 1)

    def test_image_unsupported(self):
        path = 'tests/images/SHAKA.PNG'
        self.assertRaises(UnsupportedPhoneModel, GymBadge, path)

    #==========================================================================
    def test_title(self):
        self.assertEqual(self.im01.get_title(), 'third ward park playground')

    #==========================================================================
    def test_activity(self):
        self.assertEqual(
            self.im02.get_gym_activity(uid=1000), 
            {'victories':18, 'days':25, 'hours':18, 'minutes':1, 'treats':9}
            )

    def test_activity_manual(self):
        unittest.mock.builtins.input = lambda _: ""
        pass

if __name__ == '__main__':
    unittest.main()