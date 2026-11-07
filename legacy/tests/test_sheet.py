import unittest
import unittest.mock

import pytest

from PokemonGo.sheet import GymSheet
from PokemonGo.exceptions import TitleNotFound
from gspread import SpreadsheetNotFound


class SheetTests(unittest.TestCase):
    """
    Test the process of accessing spreadsheet and methods for locating 
    gym titles.

    .. warning::
        Tests may not pass if spreadsheet state is changed. If tests fail, 
        please verify the row index values in each test.
    """
    
    def setUp(self):
        self.key = 'requirements/pogo_gyms_314413.json'
        name = 'gym_data'
        self.gs = GymSheet(self.key, name)

    #==========================================================================

    @pytest.mark.order(1)
    def test_invalid_sheet_name(self):
        """
        Verify an invalid sheet name raises the appropriate `gspread` error.
        """

        self.assertRaises(
            SpreadsheetNotFound, 
            GymSheet, 
            self.key, 'InvalidName'
            )

    #==========================================================================

    @pytest.mark.order(2)
    def test_find_new_unique(self):
        """
        Verify simple case of finding a new, unique title in the spreadsheet.
        """

        title = 'z_test_new_gym'

        ans = self.gs.find(title)
        self.assertEqual(ans, (title, 1405))

        # The title doesn't have to be exact to find match.
        unittest.mock.builtins.input = lambda _: "y"
        ans = self.gs.find('z_tes1_new_gym')
        self.assertEqual(ans, (title, 1405))

    #==========================================================================

    @pytest.mark.order(3)
    def test_find_update(self):
        """
        Verity process for locating previously scanned images. If used 
        incorrectly, default values are returned along with logging error.
        """
        
        title = 'the church of jesus christ of latter-day saints'

        # Incorrect way of locating previously scanned images.
        ans = self.gs.find(title)
        self.assertEqual(ans[0], '')
        self.assertEqual(ans[1], -1)
        self.assertEqual(self.gs.errors[0], 'TITLE')

        # Correct way of located previously scanned images.
        ans = self.gs.find(title, isUpdate=True)
        self.assertEqual(ans, (title, 131))

    @pytest.mark.order(4)
    def test_find_with_duplicates(self):
        """
        Verify process for finding new titles with multiple matches. This 
        process raises error if the user makes a mistake..
        """

        # Mock up the response to the desired row index.
        unittest.mock.builtins.input = lambda _: "60"
        ans = self.gs.find('verizon', isUpdate=True)
        self.assertEqual(ans, ('verizon', 60))

        # Mock up the response to the desired row index.
        unittest.mock.builtins.input = lambda _: "1"
        self.assertRaises(
            TitleNotFound, 
            self.gs.find, 
            'verizon', True
        )

#==========================================================================

if __name__ == '__main__':
    unittest.main()