import unittest
import unittest.mock

import pytest

from PokemonGo.gym import GoldGym
from geopy.exc import ConfigurationError
from PokemonGo.exceptions import ArgumentError


class GymTests(unittest.TestCase):
    def setUp(self):
        self.basicGym = GoldGym(uid=1)
        self.msgOptParams = {
            'title': 'madison square garden',
            'victories': 200,
            'days': 1,
            'hours': 5,
            'minutes': 10,
            'treats': 1_000
            }
        self.MSG = GoldGym(uid=2, **self.msgOptParams)
        self.msgLatLon = '40.75067515347, -73.99339578809'
        self.email = 'lindamcmahon4u@gmail.com'   # valid email

    #==========================================================================
    @pytest.mark.order(1)
    def test_empty_instance(self):
        self.assertRaises(TypeError, GoldGym)
    
    #==========================================================================
    @pytest.mark.order(2)
    def test_params_default(self):
        self.assertEqual(
            [self.basicGym.victories, self.basicGym.treats], 
            [0, 0]
            )
    
    #==========================================================================
    @pytest.mark.order(3)
    def test_uid_char(self):
        self.assertRaises(ArgumentError, GoldGym, 'a')
    
    @pytest.mark.order(4)
    def test_uid_float(self):
        self.assertRaises(ArgumentError, GoldGym, 1.5)

    #==========================================================================
    @pytest.mark.order(5)
    def test_attribute_setter(self):
        self.assertRaises(ArgumentError, self.basicGym.set_victories, 10.5)

    #==========================================================================
    @pytest.mark.order(6)
    def test_style(self):
        self.MSG.set_style()
        self.assertEqual(self.MSG.style, 'gold')

    @pytest.mark.order(7)
    def test_style_long_term(self):
        self.basicGym.set_days(1_001)
        self.basicGym.set_style()
        self.assertEqual(self.basicGym.style, '100+ days')
    
    #==========================================================================
    @pytest.mark.order(8)
    def test_latlon_value(self):
        self.assertRaises(
            ValueError, 
            self.basicGym.set_address, 
            latlon = 'a',   # invalid value
            email = self.email
        )
    
    @pytest.mark.order(9)
    def test_latlon_components(self):
        # geolocator.reverse -> None
        self.assertRaises(
            AttributeError, 
            self.basicGym.set_address, 
            latlon = '3,4',   # invalid `lat,lon`
            email = self.email
        )
    
    #==========================================================================
    @pytest.mark.order(10)
    def test_address_wo_params(self):
        self.assertRaises(TypeError, self.basicGym.set_address)

    @pytest.mark.order(11)
    def test_address_wo_email(self):
        self.assertRaises(
            TypeError, 
            self.basicGym.set_address, 
            latlon = self.msgLatLon
            )
    
    @pytest.mark.order(12)
    def test_address_email_invalid(self):
        self.assertRaises(
            ConfigurationError, 
            self.basicGym.set_address, 
            latlon = self.msgLatLon, 
            email = None
            )

    #==========================================================================
    @pytest.mark.order(13)
    def test_city_before_address(self):
        self.assertRaises(AttributeError, self.MSG.set_city)

    @pytest.mark.order(14)
    def test_city(self):
        self.MSG.set_address(self.msgLatLon, self.email)
        self.MSG.set_city()
        self.assertEqual(self.MSG.city, 'city of new york')

    @pytest.mark.order(15)
    def test_city_w_input(self):
        # use remote location (Wilderness State Park, MI)
        self.basicGym.set_address(
            '45.74127368988, -84.92224540493',
            self.email
            )
        # mock up user response
        unittest.mock.builtins.input = lambda _: "carp lake"
        self.basicGym.set_city()
        self.assertEqual(self.basicGym.errors[0], 'CITY')

    #==========================================================================
    @pytest.mark.order(16)
    def test_county_strip(self):
        # the word `county` should not appear
        self.MSG.set_address(self.msgLatLon, self.email)
        self.MSG.set_county()
        self.assertNotEqual(self.MSG.county, 'new york county')


if __name__ == '__main__':
    unittest.main()