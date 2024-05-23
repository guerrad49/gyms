"""
This module contains custom exceptions to be raised within the
PokemonGo package.
"""


class InvalidEnvironment(Exception):
    def __str__(self) -> str:
        msg = 'one or more environment variables not set'
        return msg

class UnsupportedPhoneModel(Exception):
    def __str__(self) -> str:
        msg = 'image was not created by a supported phone model'
        return msg

class InputError(Exception):
    def __str__(self) -> str:
        msg = 'invalid input provided by user'
        return msg

class ArgumentError(Exception):
    def __str__(self) -> str:
        msg = 'argument must be <int> type'
        return msg