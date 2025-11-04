"""
PokemonGo.gym
-------------

This module contains GoldGym class for compiling a PokemonGo 
gym's data in one location. Manually set attributes are used 
to automate setting other attributes. The setter methods 
show use-cases for this process.
"""


from typing import Optional

from geopy.geocoders import Nominatim


HRS_IN_DAY  = 24
MINS_IN_DAY = 1440
LONG_TERM_DEFENDING = 100   # Unit = days.


class GoldGym:
    """
    Class to manage PokemonGo gym-related attributes.

    Examples
    --------
    >>> # Instance w/o parameters.
    >>> aa = GoldGym()
    >>> 
    >>> # Instance w/ all optional parameters.
    >>> bb = GoldGym(title='sydney opera house', 
    ...     victories=100, days=10, hours=7,
    ...     minutes=20, treats=500)
    >>> 
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
        
        """
        Parameters
        ----------
        title:
            The gym title.
        victories:
            The number of victories at a gym.
        days:
            The number of days defending a gym.
        hours:
            The number of additional hours defending a gym.
        minutes:
            The number of additional minutes defending a gym.
        treats:
            The number of treats fed at a gym.
        errors:
            The list of processing errors.
        """

    def __setattr__(self, name, value):
        """Check specific attributes for typing."""

        if name in self._intFields and not isinstance(value, int):
            msg = "Attribute '{}' must be an <class 'int'>".format(name)
            raise TypeError(msg)
        super().__setattr__(name, value)


    def set_time_defended(self) -> None:
        """
        Compute total time defended (in days) from time attributes.
        """

        totalDays = self.days
        totalDays += self.hours / HRS_IN_DAY
        totalDays += self.minutes / MINS_IN_DAY

        self.defended = round(totalDays, 4)


    def set_style(self) -> None:
        """
        Determine gym style based on number of days defended.
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
        Set address dictionary.

        Parameters
        ----------
        latlon:
            The known coordinates in `lat,long` format.
        email:
            The user's email required by third party ToS.
        
        See Also
        --------
        geopy.geocoders.Nominatim
        """

        self.latlon = latlon
        geolocator  = Nominatim(user_agent=email)

        # [latitude, longitude]
        coordinates = [x.strip() for x in self.latlon.split(',')]

        location     = geolocator.reverse(coordinates)
        self.address = location.raw['address']

        if not self.address:
            self.errors.append('ADDRESS')


    def set_city(self) -> None:
        """
        Set the gym's city from address.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError
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
        Set the gym's county from address.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError
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
        Set the gym's state from address.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError
        """

        try:
           state = self.address['state']
        except KeyError:
            self.errors.append('STATE')
            # Manually enter state name (rare in US).
            prompt = 'Enter STATE for `{}`:\t'.format(self.latlon)
            state = input(prompt).strip()

        self.state = state.lower()
