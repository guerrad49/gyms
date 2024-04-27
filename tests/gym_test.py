import unittest
import unittest.mock

import pytest

from PokemonGo.gym import GoldGym
from PokemonGo.exceptions import ArgumentError
from geopy.exc import ConfigurationError


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
        self.msg = GoldGym(uid=2, **self.msgOptParams)
        self.msgLatLon = '40.75067515347, -73.99339578809'
        self.email = 'lindamcmahon4u@gmail.com'   # valid email

    #================================================================
    @pytest.mark.order(1)
    def test_empty_instance(self):
        self.assertRaises(TypeError, GoldGym)
    
    #================================================================
    @pytest.mark.order(2)
    def test_params_default(self):
        self.assertEqual(
            [self.basicGym.victories, self.basicGym.treats], 
            [0, 0]
            )

    @pytest.mark.order(3)
    def test_params_as_strings(self):
        strParams = {
            k:str(v) for k,v in self.msgOptParams.items()
            }
        gg = GoldGym(uid=3, **strParams)
        self.assertEqual(
            [gg.uid, gg.days, gg.minutes], [3, 1, 10]
            )
    
    @pytest.mark.order(4)
    def test_param_type_invalid(self):
        self.assertRaises(
            ArgumentError, 
            GoldGym, uid=4, days=3.3
            )

    #================================================================
    @pytest.mark.order(5)
    def test_uid_char(self):
        self.assertRaises(ArgumentError, GoldGym, 'a')
    
    @pytest.mark.order(6)
    def test_uid_float(self):
        self.assertRaises(ArgumentError, GoldGym, 1.5)

    #================================================================
    @pytest.mark.order(7)
    def test_victories_set(self):
        self.assertRaises(
            ArgumentError, 
            self.basicGym.set_victories, 10.5
            )

    #================================================================
    @pytest.mark.order(8)
    def test_style(self):
        self.msg.set_style()
        self.assertEqual(self.msg.style, 'gold')

    @pytest.mark.order(9)
    def test_style_long_term(self):
        self.basicGym.set_days(1_001)
        self.basicGym.set_style()
        self.assertEqual(self.basicGym.style, '100+ days')
    
    #================================================================
    @pytest.mark.order(10)
    def test_latlon_value(self):
        self.assertRaises(
            ValueError, 
            self.basicGym.set_address, 
            latlon = 'a',   # invalid value
            email = self.email
        )
    
    @pytest.mark.order(11)
    def test_latlon_components(self):
        # geolocator.reverse -> None
        self.assertRaises(
            AttributeError, 
            self.basicGym.set_address, 
            latlon = '3,4',   # invalid `lat,lon`
            email = self.email
        )
    
    #================================================================
    @pytest.mark.order(12)
    def test_address_wo_params(self):
        self.assertRaises(TypeError, self.basicGym.set_address)

    @pytest.mark.order(13)
    def test_address_wo_email(self):
        self.assertRaises(
            TypeError, 
            self.basicGym.set_address, 
            latlon = self.msgLatLon
            )
    
    @pytest.mark.order(14)
    def test_address_email_invalid(self):
        self.assertRaises(
            ConfigurationError, 
            self.basicGym.set_address, 
            latlon = self.msgLatLon, 
            email = None
            )

    #================================================================
    @pytest.mark.order(15)
    def test_city_before_address(self):
        self.assertRaises(AttributeError, self.msg.set_city)

    @pytest.mark.order(16)
    def test_city(self):
        self.msg.set_address(self.msgLatLon, self.email)
        self.msg.set_city()
        self.assertEqual(self.msg.city, 'city of new york')

    @pytest.mark.order(17)
    def test_city_remote(self):
        # use remote location (Wilderness State Park, MI)
        self.basicGym.set_address(
            '45.74127368988, -84.92224540493',
            self.email
            )
        # mock up user response
        unittest.mock.builtins.input = lambda _: "carp lake"
        self.basicGym.set_city()
        self.assertEqual(self.basicGym.city, 'carp lake')

    #================================================================
    @pytest.mark.order(18)
    def test_county_strip(self):
        # the word `county` should not appear
        self.msg.set_address(self.msgLatLon, self.email)
        self.msg.set_county()
        self.assertNotEqual(self.msg.county, 'new york county')

    #================================================================
    @pytest.mark.order(19)
    def test_values_address(self):
        self.msg.set_defended()
        self.msg.set_style()
        self.msg.set_address(self.msgLatLon, self.email)
        self.msg.set_city()
        self.msg.set_county()
        self.msg.set_state()
        v = list(self.msg)
        self.assertEqual(
            v[8:10], 
            [self.msg.treats, self.msg.latlon]
            )


if __name__ == '__main__':
    unittest.main()