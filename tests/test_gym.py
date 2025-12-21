import unittest
import unittest.mock

import pytest

from PokemonGo.gym import GoldGym
from geopy.exc import ConfigurationError


class GymTest(unittest.TestCase):
    """
    Test the behavior of GoldGym class setters.
    """

    def setUp(self):
        self.testGym = GoldGym()
        self.msgOptParams = {
            'title': 'madison square garden',
            'victories': 200,
            'days': 1,
            'hours': 5,
            'minutes': 10,
            'treats': 1_000
            }
        self.MSG = GoldGym(**self.msgOptParams)
        self.msgLatLon = '40.75067515347, -73.99339578809'
        self.email = 'lindamcmahon4u@gmail.com'   # Valid email.

    #==========================================================================

    @pytest.mark.order(1)
    def test_empty_instance(self):
        """
        Verify an empty instance has default attribute values.
        """

        self.assertEqual(self.testGym.title, '')
        self.assertEqual(self.testGym.victories, 0)
        self.assertEqual(self.testGym.days, 0)
        self.assertEqual(self.testGym.defended, 0)
        self.assertEqual(len(self.testGym.errors), 0)
        
    #==========================================================================
    
    @pytest.mark.order(2)
    def test_setting_int_fields(self):
        """
        Verify attributes defined in `_intField` cannot be assigned non 
        **int** types. Even integer strings (i.e. "20") are invalid.
        """

        self.assertRaises(TypeError, self.testGym.victories, 10.5)
        self.assertRaises(TypeError, self.testGym.days, 'a')
        self.assertRaises(TypeError, self.testGym.treats, "20")

    #==========================================================================

    @pytest.mark.order(3)
    def test_set_style(self):
        """
        Verify `set_style` behavior depends on `days` value.
        """

        # Gym defended less than 100 days.
        self.MSG.set_style()
        self.assertEqual(self.MSG.style, 'gold')

        # Gym defended 100 days.
        self.testGym.days = 100
        self.testGym.set_style()
        self.assertEqual(self.testGym.style, '100+ days')
    
    #==========================================================================

    @pytest.mark.order(4)
    def test_set_address_email(self):
        """
        Verify valid `email` parameter is given in `set_address`. This is 
        required for Nominatim to obtain address from coordinates.
        """

        # Omit email.
        self.assertRaises(
            TypeError, 
            self.testGym.set_address, 
            latlon = self.msgLatLon
            )
    
        # Email must be a string.
        self.assertRaises(
            ConfigurationError, 
            self.testGym.set_address, 
            latlon = self.msgLatLon, 
            email = None
            )

    #==========================================================================
    
    @pytest.mark.order(5)
    def test_set_address_latlon(self):
        """
        Verify correct and incorrect use of `set_address` with valid and 
        invalid lalon parameter values.
        """

        # Latlon must be comma separated coordinates.
        self.assertRaises(
            ValueError, 
            self.testGym.set_address, 
            latlon = 'a', 
            email = self.email
        )

        # Latlon format is correct but invalid coordinate values.    
        self.assertRaises(
            AttributeError, 
            self.testGym.set_address, 
            latlon = '3,4', 
            email = self.email
        )

        # Valid parameter values.
        self.MSG.set_address(self.msgLatLon, self.email)
        self.assertGreater(len(self.MSG.address), 0)
    
    #==========================================================================

    @pytest.mark.order(6)
    def test_set_city(self):
        """
        Verify `set_city` fails if `address` is not set and succeeds 
        otherwise. Locations that require user-input will add to `errors` 
        attribute appropriately.
        """

        # Cannot use set_city prior to set_address.
        self.assertRaises(AttributeError, self.testGym.set_city)

        # This is normal behavior.
        self.MSG.set_address(self.msgLatLon, self.email)
        self.MSG.set_city()
        self.assertEqual(self.MSG.city, 'city of new york')

        # Use remote location in High Peaks Wilderness (upstate NY).
        self.testGym.set_address(
            '44.109394, -74.317468',
            self.email
            )
        # Mock up user response.
        unittest.mock.builtins.input = lambda _: "some town"
        self.testGym.set_city()
        self.assertEqual(self.testGym.city, 'some town')
        self.assertEqual(self.testGym.errors[0], 'CITY')

#==========================================================================

if __name__ == '__main__':
    unittest.main()