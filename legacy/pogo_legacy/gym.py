"""
PokemonGo.gym
-------------

This module contains the GoldGym class for storing a gold gym's data 
values in one location.
"""


from typing import Optional

from geopy.geocoders import Nominatim


HRS_IN_DAY  = 24
MINS_IN_DAY = 1440
LONG_TERM_DEFENDING = 100   # Unit = days.


class GoldGym:
    """
    Class to manage PokemonGo gym-related attributes.

    :param str title: (optional) The gym title.
    :param int victories: (optional) The number of victories.
    :param int days: (optional) The number of days defending.
    :param int hours: (optional) The number of hours defending.
    :param int minutes: (optional) The number of minutes defending.
    :param int treats: (optional) The number of treats.

    Examples:

    .. code:: python

        >>> # Instance w/o parameters.
        >>> aa = GoldGym()

        >>> # Instance w/ all optional parameters.
        >>> bb = GoldGym(title='sydney opera house', 
        ...     victories=100, days=10, hours=7,
        ...     minutes=20, treats=500)

        >>> # Instance w/ unpacking dictionary of parameters.
        >>> params = {
        ...     'title': '大阪城', 'victories': 246, 'days': 2, 
        ...     'hours': 3, 'minutes': 40, 'treats': 369
        ...     }
        >>> cc = GoldGym(**params)
    """

    _intFields = {
        "victories", "days", "hours", "minutes", "treats"
        }
    
    def __init__(
        self, 
        title:     Optional[str] = '',
        victories: Optional[int] = 0,
        days:      Optional[int] = 0,
        hours:     Optional[int] = 0,
        minutes:   Optional[int] = 0,
        treats:    Optional[int] = 0
        ) -> None:
        self.title     = title
        self.style     = None
        self.victories = victories
        self.days      = days
        self.hours     = hours
        self.minutes   = minutes
        self.defended  = 0
        self.treats    = treats
        self.errors    = list()
    

    def __setattr__(self, name, value):
        """Check integer attributes for typing."""

        if name in self._intFields and not isinstance(value, int):
            msg = "Attribute '{}' must be an <class 'int'>".format(name)
            raise TypeError(msg)
        super().__setattr__(name, value)


    def set_time_defended(self) -> None:
        """
        Compute the total time defended (in days) from defending attributes.
        """

        totalDays = self.days
        totalDays += self.hours / HRS_IN_DAY
        totalDays += self.minutes / MINS_IN_DAY

        self.defended = round(totalDays, 4)


    def set_style(self) -> None:
        """
        Determine gym style from number of days defended.
        """

        if self.days < LONG_TERM_DEFENDING:
            self.style = 'gold'
        else:
            self.style = '100+ days'


    def set_address(
            self, 
            latlon: str, 
            email: str
            ) -> None:
        """
        Set address dictionary from coordinates using 
        :class:`geopy.geocoders.Nominatim`.

        :param str latlon: The known coordinates in `lat,long` format.
        :param str email: The user email required by third party ToS.
        """

        self.latlon = latlon

        # Increase timeout to handle slow responses from Nominatim.
        geolocator  = Nominatim(user_agent=email, timeout=5)
        # (Latitude, Longitude)
        coordinates = tuple( x.strip() for x in self.latlon.split(',') )

        location     = geolocator.reverse(coordinates)
        self.address = location.raw['address']

        if not self.address:
            self.errors.append('ADDRESS')


    def set_city(self) -> None:
        """
        Set the gym's city from address. Users should make prior call to 
        :meth:`GoldGym.set_address`.
        
        :raises AttributeError: if :attr:`GoldGym.address` not set.
        """

        city = None

        # Common options seen in Nominatim.
        for option in ['city','town','village','township']:
            if option in self.address.keys():
                city = self.address[option]
        
        if not city:
            self.errors.append('CITY')
            # Manually enter city name.
            prompt = 'Enter CITY for `{}`:\t'.format(self.latlon)
            city   = input(prompt).strip()

        self.city = city.lower()


    def set_county(self) -> None:
        """
        Set the gym's county from address. Users should make prior call to 
        :meth:`GoldGym.set_address`.
        
        :raises AttributeError: if :attr:`GoldGym.address` not set.
        """

        try:
            county = self.address['county']
        except KeyError:
            self.errors.append('COUNTY')
            # Manually enter county name.
            prompt = 'Enter COUNTY for `{}`:\t'.format(self.latlon)
            county = input(prompt).strip()
        
        county = county.lower()
        self.county = county.removesuffix(' county')


    def set_state(self) -> None:
        """
        Set the gym's state from address. Users should make prior call to 
        :meth:`GoldGym.set_address`.
        
        :raises AttributeError: if :attr:`GoldGym.address` not set.
        """

        try:
           state = self.address['state']
        except KeyError:
            self.errors.append('STATE')
            # Manually enter state name (rare in US).
            prompt = 'Enter STATE for `{}`:\t'.format(self.latlon)
            state = input(prompt).strip()

        self.state = state.lower()
