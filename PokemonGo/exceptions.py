"""
This module contains custom exceptions to be raised within the
PokemonGo package.
"""


class UnsupportedPhoneModel(Exception):
    def __str__(self) -> str:
        msg = 'image was not created by a supported phone model'
        return msg

class InputError(Exception):
    def __str__(self) -> str:
        msg = 'invalid input provided by user'
        return msg