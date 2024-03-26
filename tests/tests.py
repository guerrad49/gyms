import sys
# caution: path[0] is reserved for script path (or '' in REPL)
sys.path.insert(1, '/Users/david_guerra/Documents/Programming/python/gyms')

import unittest

import pandas as pd
from gyms import Gym

BADGES = '/Users/david_guerra/Documents/Programming/python/gyms/badges'

class TestBirthday(unittest.TestCase):
    def setUp(self):
        self.df = pd.read_csv('test.csv', index_col=0)
        self.img01 = Gym('IMG_1187.PNG', self.df)

    def some_test(self):
        pass
        

if __name__ == '__main__':
    unittest.main()