import unittest
import unittest.mock

import pytest

from PokemonGo.image import BadgeImage
from PokemonGo.utils import are_similar
from PokemonGo.exceptions import UnsupportedPhoneModel, InputError


class ImageTests(unittest.TestCase):
    def setUp(self):
        # Starbucks.
        self.img01 = BadgeImage('tests/images/IMG_0001.PNG')
        # Portland Head Light.
        self.img02 = BadgeImage('tests/images/IMG_0002.PNG')
        # The Church of Jesus Christ of Latter-Day Saints.
        self.img03 = BadgeImage('tests/images/IMG_0003.PNG')

    #==========================================================================

    @pytest.mark.order(1)
    def test_empty_instance(self):
        """
        Verify instantiating without `path` raises error.
        """

        self.assertRaises(TypeError, BadgeImage)

    #==========================================================================

    @pytest.mark.order(2)
    def test_phone_models(self):
        """
        Verify iPhone models are set using image dimensions or raise error 
        if dimensions are not in available models.
        """

        self.assertEqual(self.img01.params.model, 'iSE')
        self.assertEqual(self.img02.params.model, 'i11')
        self.assertEqual(self.img03.params.model, 'i15')

        path = 'tests/images/SHAKA.PNG'
        self.assertRaises(UnsupportedPhoneModel, BadgeImage, path)

    #==========================================================================

    @pytest.mark.order(3)
    def test_title_simple(self):
        """
        Verify reading single-lined, short title returns exact match.
        """

        self.img01.set_title_crop()
        title = self.img01.get_text(region='title')
        self.assertEqual(title, 'starbucks')

    @pytest.mark.order(4)
    def test_title_multilined(self):
        """
        Verify process for reading multi-lined titles. Often, the phone 
        status bar affects reading an exact match. Some issues are 
        self-corrected with the use of build-in methods.
        """

        # The ground truth title.
        answer = 'the church of jesus christ of latter-day saints'

        # Try reading as-is.
        self.img03.set_title_crop()
        scannedTitle = self.img03.get_text(region='title')
        # The output is not similar enough.
        self.assertFalse( are_similar(scannedTitle, answer) )

        # Try again by modifying process.
        self.img03.set_title_crop(offset=40)
        self.img03.soften_title_overlay()
        scannedTitle = self.img03.get_text(region='title')
        # The output is now very similar.
        unittest.mock.builtins.input = lambda _: "y"
        self.assertTrue( are_similar(scannedTitle, answer) )

    #==========================================================================

    @pytest.mark.order(5)
    def test_activity_simple(self):
        """
        Verify process for reading activity values with exact match.
        """

        self.img03.set_activity_crop()
        activityTxt = self.img03.get_text(region='activity')
        activityDict = self.img03.get_activity_vals(activityTxt)
        self.assertEqual(
            activityDict, 
            {'victories':8, 'days':21, 'hours':19, 'minutes':0, 'treats':13}
            )
        
    @pytest.mark.order(6)
    def test_activity_correction(self):
        """
        Verify process for reading activity values that requires correction. 
        Cases are designed to raise errors and simulate ability to fix 
        mistakes with and without user input.
        """

        answer = {
            'victories':0, 'days':21, 'hours':18, 'minutes':7, 'treats':104
            }

        # Other errors require user input.
        activityTxt = "o 21d 18h 7m 104"
        # Preload with user response.
        unittest.mock.builtins.input = lambda _: "0 21d 18h 7m 104"
        activityDict = self.img02.get_activity_vals(activityTxt)
        self.assertEqual(activityDict, answer)
        # The error is recorded.
        self.assertEqual(self.img02.errors[0], 'STATS')

        # If the user gives a bad response...
        unittest.mock.builtins.input = lambda _: "O 21d 18h 7n 104"
        # An error is raised.
        self.assertRaises(
            InputError, self.img02.get_activity_vals, activityTxt
            )

#==========================================================================

if __name__ == '__main__':
    unittest.main()