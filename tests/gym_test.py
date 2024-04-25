import os
import unittest

from PokemonGo.gym import GoldGym
from PokemonGo.exceptions import ArgumentError


class GymTests(unittest.TestCase):
    def setUp(self):
        self.uid = 1
        self.params = {
            'uid': 2,
            'title': 'madison square garden',
            'victories': 1_000,
            'days': 1,
            'hours': 5,
            'minutes': 10,
            'treats': 200
            }
        self.coords = '40.75067515347156, -73.99339578809071'
        self.email = 'lindamcmahon4u@gmail.com'   # valid email

    def test_empty_gg(self):
        self.assertRaises(TypeError, GoldGym)

    def test_invalid_uid_1(self):
        self.assertRaises(ArgumentError, GoldGym, 'a')
    
    def test_invalid_uid_2(self):
        self.assertRaises(ArgumentError, GoldGym, 1.5)

    def test_gg_w_uid_only(self):
        gg = GoldGym(self.uid)
        self.assertEqual(gg.treats, 0)

    def test_gg_valid_params(self):
        gg = GoldGym(**self.params)
        self.assertEqual(gg.victories, 1000)

    def test_gg_invalid_param(self):
        self.assertRaises(ArgumentError, GoldGym, self.uid, days=3.3)

    def test_style(self):
        gg = GoldGym(**self.params)
        gg.set_style()
        self.assertEqual(gg.style, 'gold')

    def test_long_term_style(self):
        gg = GoldGym(1, days=1_001)
        gg.set_style()
        self.assertEqual(gg.style, '100+ days')

    def test_city_wo_address(self):
        gg = GoldGym(**self.params)
        self.assertRaises(AttributeError, gg.set_city)

    def test_city(self):
        gg = GoldGym(**self.params)
        gg.set_address(self.coords, self.email)
        gg.set_city()
        self.assertEqual(gg.city, 'city of new york')


if __name__ == '__main__':
    unittest.main()