import unittest
import unittest.mock

import pytest

from PokemonGo.google_sheet import GoogleSheet

# TODO: Write tests cases once GoogleSheet can take in dataframe.

class SheetTests(unittest.TestCase):
    def setUp(self):
        key = 'subfiles/pogo_gyms_314413.json'
        name = 'gym_data'
        self.gs = GoogleSheet(key, name)

    #==========================================================================
    @pytest.mark.order(1)
    def test_empty_instance(self):
        self.assertRaises(TypeError, GoogleSheet)

    #==========================================================================
    @pytest.mark.order(2)
    def test_find_none(self):
        self.assertRaises(TypeError, self.gs.find)

    @pytest.mark.order(3)
    def test_find_exact(self):
        # searching over processed
        self.assertEqual(
            self.gs.find('fish sculpture', new=False),
            ('fish sculpture', 12)
        )

    @pytest.mark.order(4)
    def test_find_similar(self):
        """Title is misspelled. User accepts correction."""

        # mock up user response
        unittest.mock.builtins.input = lambda _: "y"
        ans = self.gs.find('fish scu1pture', new=False)
        self.assertEqual(ans, ('fish sculpture', 12))

    @pytest.mark.order(5)
    def test_find_duplicates(self):
        """Title has 5 duplicates. User chooses first index."""

        # mock up user response
        unittest.mock.builtins.input = lambda _: "588"
        ans = self.gs.find('morris canal marker', new=False)
        self.assertEqual(ans, ('morris canal marker', 588))

if __name__ == '__main__':
    unittest.main()