import unittest
import unittest.mock

from PokemonGo.gym import GoldGym
from PokemonGo.exceptions import ArgumentError


class GymTests(unittest.TestCase):
    def setUp(self):
        self.uid = 2
        self.BGG = GoldGym(self.uid)   # minimun required
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

    def test_empty_instance(self):
        self.assertRaises(TypeError, GoldGym)
    
    def test_defaul_params(self):
        # use a Basic Gold Gym
        self.assertEqual(
            [self.BGG.victories, self.BGG.treats], [0, 0]
            )
        
    def test_instance_w_str_params(self):
        str_params = {
            k:str(v) for k,v in self.params.items()
            }
        gg = GoldGym(**str_params)
        self.assertEqual(
            [gg.uid, gg.days, gg.minutes], [1, 1, 10]
            )

    def test_char_uid(self):
        self.assertRaises(ArgumentError, GoldGym, 'a')
    
    def test_float_uid(self):
        self.assertRaises(ArgumentError, GoldGym, 1.5)

    def test_gg_invalid_param(self):
        self.assertRaises(ArgumentError, GoldGym, self.uid, days=3.3)

    def test_style(self):
        self.MSG.set_style()
        self.assertEqual(self.MSG.style, 'gold')

    def test_long_term_style(self):
        gg = GoldGym(self.uid, days=1_001)
        gg.set_style()
        self.assertEqual(gg.style, '100+ days')

    def test_city_wo_address(self):
        self.assertRaises(AttributeError, self.MSG.set_city)

    def test_city(self):
        self.MSG.set_address(self.coords, self.email)
        self.MSG.set_city()
        self.assertEqual(self.MSG.city, 'city of new york')

    def test_city_w_input(self):
        wsp = GoldGym(self.uid)
        wsp.set_address(
            '45.74127368988119, -84.92224540493795',
            self.email
            )
        unittest.mock.builtins.input = lambda _: "carp lake"
        wsp.set_city()
        self.assertEqual(wsp.city, 'carp lake')

if __name__ == '__main__':
    unittest.main()