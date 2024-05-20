import unittest
import unittest.mock

import pytest

from PokemonGo.image import GymBadge
from PokemonGo.exceptions import UnsupportedPhoneModel, InputError


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.im01 = GymBadge('tests/images/IMG_0001.PNG')
        self.im02 = GymBadge('tests/images/IMG_0002.PNG')
        self.im03 = GymBadge('tests/images/IMG_0003.PNG')

    #==========================================================================
    @pytest.mark.order(1)
    def test_empty_instance(self):
        self.assertRaises(TypeError, GymBadge)

    #==========================================================================
    @pytest.mark.order(2)
    def test_model_ise(self):
        self.assertEqual(self.im01.model, 'iSE')

    @pytest.mark.order(3)
    def test_model_i11(self):
        self.assertEqual(self.im02.model, 'i11')

    @pytest.mark.order(4)
    def test_model_i15(self):
        self.assertEqual(self.im03.model, 'i15')

    @pytest.mark.order(5)
    def test_model_unsupported(self):
        path = 'tests/images/SHAKA.PNG'
        self.assertRaises(UnsupportedPhoneModel, GymBadge, path)

    #==========================================================================
    @pytest.mark.order(6)
    def test_title(self):
        self.assertEqual(self.im03.get_title(), 'tulip mural')

    #==========================================================================
    @pytest.mark.order(7)
    def test_activity(self):
        self.assertEqual(
            self.im03.get_gym_activity(), 
            {'victories':21, 'days':17, 'hours':17, 'minutes':0, 'treats':501}
            )

    @pytest.mark.order(8)
    def test_activity_input_good(self):
        # mock up user response
        unittest.mock.builtins.input = lambda _: "11 19d 5h 1m 17"
        self.im02.get_gym_activity()
        self.assertEqual(self.im02.errors[0], 'STATS')
    
    @pytest.mark.order(9)
    def test_activity_input_bad(self):
        # mock up user response
        unittest.mock.builtins.input = lambda _: "11 19d th 1m 17"
        self.assertRaises(
            InputError, self.im02.get_gym_activity
            )


if __name__ == '__main__':
    unittest.main()