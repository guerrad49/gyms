import unittest
import unittest.mock

import pytest

from PokemonGo.gym import GoldGym
from PokemonGo.exceptions import ArgumentError
from geopy.exc import ConfigurationError


class GymTests(unittest.TestCase):
    def setUp(self):
        self.uid = 2
        self.basic_gym = GoldGym(self.uid)
        self.params = {
            'uid': 1,
            'title': 'madison square garden',
            'victories': 200,
            'days': 1,
            'hours': 5,
            'minutes': 10,
            'treats': 1_000
            }
        self.MSG = GoldGym(**self.params)
        self.coords = '40.75067515347156, -73.99339578809071'
        self.email = 'lindamcmahon4u@gmail.com'   # valid email

    #================================================================
    @pytest.mark.order(1)
    def test_empty_instance(self):
        self.assertRaises(TypeError, GoldGym)
    
    #================================================================
    @pytest.mark.order(2)
    def test_params_default(self):
        self.assertEqual(
            [self.basic_gym.victories, self.basic_gym.treats], 
            [0, 0]
            )

    @pytest.mark.order(3)
    def test_params_as_strings(self):
        str_params = {
            k:str(v) for k,v in self.params.items()
            }
        gg = GoldGym(**str_params)
        self.assertEqual(
            [gg.uid, gg.days, gg.minutes], [1, 1, 10]
            )
    
    @pytest.mark.order(4)
    def test_param_type_invalid(self):
        self.assertRaises(ArgumentError, GoldGym, self.uid, days=3.3)

    #================================================================
    @pytest.mark.order(5)
    def test_uid_char(self):
        self.assertRaises(ArgumentError, GoldGym, 'a')
    
    @pytest.mark.order(6)
    def test_uid_float(self):
        self.assertRaises(ArgumentError, GoldGym, 1.5)

    #================================================================
    @pytest.mark.order(7)
    def test_style(self):
        self.MSG.set_style()
        self.assertEqual(self.MSG.style, 'gold')

    @pytest.mark.order(8)
    def test_style_long_term(self):
        gg = GoldGym(self.uid, days=1_001)
        gg.set_style()
        self.assertEqual(gg.style, '100+ days')
    
    #================================================================
    @pytest.mark.order(9)
    def test_coordinates_format(self):
        self.assertRaises(
            ValueError, 
            self.basic_gym.set_address, 
            coordinates = 'a',   # invalid format
            email = self.email
        )
    
    @pytest.mark.order(10)
    def test_coordinates_components(self):
        # geolocator.reverse -> None
        self.assertRaises(
            AttributeError, 
            self.basic_gym.set_address, 
            coordinates = '3,4',   # invalid `lat,lon`
            email = self.email
        )
    
    #================================================================
    @pytest.mark.order(10)
    def test_address_wo_params(self):
        self.assertRaises(TypeError, self.basic_gym.set_address)

    @pytest.mark.order(11)
    def test_address_wo_email(self):
        self.assertRaises(
            TypeError, 
            self.basic_gym.set_address, 
            coordinates = self.coords
            )
    
    @pytest.mark.order(12)
    def test_address_email_invalid(self):
        self.assertRaises(
            ConfigurationError, 
            self.basic_gym.set_address, 
            coordinates = self.coords, 
            email = None
            )

    #================================================================
    @pytest.mark.order(13)
    def test_city_before_address(self):
        self.assertRaises(AttributeError, self.MSG.set_city)

    @pytest.mark.order(14)
    def test_city(self):
        self.MSG.set_address(self.coords, self.email)
        self.MSG.set_city()
        self.assertEqual(self.MSG.city, 'city of new york')

    @pytest.mark.order(15)
    def test_city_remote(self):
        # some locations are very remote and require user input
        wsp = GoldGym(self.uid)
        wsp.set_address(
            '45.74127368988119, -84.92224540493795',
            self.email
            )
        unittest.mock.builtins.input = lambda _: "carp lake"
        wsp.set_city()
        self.assertEqual(wsp.city, 'carp lake')

    #================================================================
    @pytest.mark.order(16)
    def test_county_strip(self):
        # the word `county` should not appear
        self.MSG.set_address(self.coords, self.email)
        self.MSG.set_county()
        self.assertNotEqual(self.MSG.county, 'new york county')

    #================================================================
    @pytest.mark.order(17)
    def test_values_address(self):
        self.MSG.set_defended()
        self.MSG.set_style()
        self.MSG.set_address(self.coords, self.email)
        self.MSG.set_city()
        self.MSG.set_county()
        self.MSG.set_state()
        v = self.MSG.values()
        self.assertNotIn('address', v)


if __name__ == '__main__':
    unittest.main()