import os
import unittest

from PokemonGo.image import Image
from PokemonGo.exceptions import UnsupportedPhoneModel


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.base = os.path.join('tests', 'images')

    def test_ise_image(self):
        path = os.path.join(self.base, 'IMG_0001.PNG')
        img  = Image(path)
        self.assertEqual(img.scale, 1.75)

    def test_i11_image(self):
        path = os.path.join(self.base, 'IMG_1000.PNG')
        img  = Image(path)
        self.assertEqual(img.scale, 1.5)

    def test_i15_image(self):
        path = os.path.join(self.base, 'IMG_1190.PNG')
        img  = Image(path)
        self.assertEqual(img.scale, 1)

    def test_unsupported_image(self):
        path = os.path.join(self.base, 'SHAKA.PNG')
        self.assertRaises(UnsupportedPhoneModel, Image, path)

if __name__ == '__main__':
    unittest.main()