"""
PokemonGo.gym
-------------

This module contains GoldGym class for compiling a gym's 
data in one location such as:
    1. Initial known gym values from database
    2. Values read using PokemonGo.BadgeImage class
    3. Methods which complete gym location values

Once all gym values are set, the best use-case is by using
`list(myGym)` as the data parameter of the `write_row`
method of PokemonGo.GoogleSheet class.

It is also recommended the use of setter class methods 
for safe-handling of class attributes.
"""


from typing import Optional, Any

from geopy.geocoders import Nominatim
from .exceptions import ArgumentError


HRS_IN_DAY = 24
MINS_IN_DAY = 1400
LONG_TERM_DEFENDING = 100   # in days


class GoldGym:
    """
    An instance of this class manages PokemonGo gym-related fields.

    Examples
    --------
    >>> # instance w/ required parameter
    >>> aa = GoldGym(1)
    >>> 
    >>> # instance w/ all optional parameters
    >>> bb = GoldGym(uid=2,
    ...     title='sydney opera house', victories=100,
    ...     days=10, hours=7, minutes=20, treats=500)
    >>> 
    >>> # instance w/ unpacking dictionary of parameters
    >>> params = {
    ...     'title': '大阪城', 'victories': 246, 
    ...     'days': 2, 'hours': 3, 'minutes': 40, 'treats': 369
    ...     }
    >>> cc = GoldGym(uid=3, **params)
    """
    
    def __init__(
        self, 
        uid:       int,
        title:     Optional[str] = None,
        victories: Optional[int] = 0,
        days:      Optional[int] = 0,
        hours:     Optional[int] = 0,
        minutes:   Optional[int] = 0,
        treats:    Optional[int] = 0
        ) -> None:
        self.uid       = self.__checkint__(uid)
        self.title     = title
        self.style     = None
        self.victories = self.__checkint__(victories)
        self.days      = self.__checkint__(days)
        self.hours     = self.__checkint__(hours)
        self.minutes   = self.__checkint__(minutes)
        self.defended  = 0
        self.treats    = self.__checkint__(treats)
        
        """
        Parameters
        ----------
        uid:
            The unique id number identifying a gym
        title:
            The gym title
        victories:
            The number of victories at a gym
        days:
            The number of days defending a gym
        hours:
            The number of additional hours defending a gym
        minutes:
            The number of additional minutes defending a gym
        treats:
            The number of treats fed at a gym
        """
    

    # TODO: move to GoogleSheet possibly
    def __iter__(self):
        """
        Overwritten to return iterable of object's 
        attribute values EXCEPT `address` value.
        """

        for key,val in self.__dict__.items():
            if key == 'address':
                pass
            else:
                yield val

    
    def __checkint__(self, x: Any) -> int:
        """Check argument type for <int>."""

        if not isinstance(x, int):
            raise ArgumentError
        return x
    

    def set_victories(self, x: int) -> None:
        """Safe setting function for victories."""

        self.victories = self.__checkint__(x)
    

    def set_days(self, x: int) -> None:
        """Safe setting function for days."""
        
        self.days = self.__checkint__(x)
    

    def set_hours(self, x: int) -> None:
        """Safe setting function for hours."""

        self.hours = self.__checkint__(x)
    

    def set_minutes(self, x: int) -> None:
        """Safe setting function for minutes."""
        
        self.minutes = self.__checkint__(x)
    

    def set_treats(self, x: int) -> None:
        """Safe setting function for treats."""
        
        self.treats = self.__checkint__(x)


    def set_time_defended(self) -> None:
        """
        Compute total time defended from time attributes. 
        Default is 0.
        """

        total = self.days + self.hours / HRS_IN_DAY \
            + self.minutes / MINS_IN_DAY

        self.defended = round(total, 4)   # in days


    def set_style(self) -> None:
        """
        Determine gym style based on number of days defended. 
        Default style is `gold`.
        """

        if self.days >= LONG_TERM_DEFENDING:
            self.style = '100+ days'
        else:
            self.style = 'gold'


    def set_address(self, latlon: str, email: str) -> None:
        """
        Set address dictionary.

        Parameters
        ----------
        latlon:
            The known coordinates in `lat,long` format
        email:
            The user's email required by third party ToS
        """

        self.latlon  = latlon
        geolocator   = Nominatim(user_agent=email)

        # proactive format clean up
        coords_list  = [x.strip() for x in self.latlon.split(',')]

        location     = geolocator.reverse(coords_list)
        self.address = location.raw['address']   # dictionary


    def set_city(self) -> None:
        """
        Set the gym's city from address.
        Note: May require user interface.
        
        See Also
        --------
        GoldGym.set_address
        """

        if 'address' not in vars(self):
            raise AttributeError('address was not set')

        city = None

        # common options address dictionary
        for option in ['city','town','village','township']:
            if option in self.address.keys():
                city = self.address[option]
        
        # manually enter city name
        # TODO: log the error
        if not city:
            prompt = 'Enter CITY for `{}`:\t'.format(self.latlon)
            city   = input(prompt).strip()

        self.city = city.lower()


    def set_county(self) -> None:
        """
        Set the gym's county from address.
        Note: May require user interface.
        
        See Also
        --------
        GoldGym.set_address
        """

        try:
            county = self.address['county']
        except AttributeError:
            raise AttributeError('address was not set')
        except KeyError:
            # manually enter county name
            # TODO: log the error
            prompt = 'Enter COUNTY for `{}`:\t'.format(self.latlon)
            county = input(prompt).strip()
        
        county = county.lower()
        self.county = county.removesuffix(' county')


    def set_state(self) -> None:
        """
        Set the gym's state from address.
        Note: May require user interface.
        
        See Also
        --------
        GoldGym.set_address
        """

        try:
           state = self.address['state']
        except AttributeError:
            raise AttributeError('address was not set')
        except KeyError:
            # manually enter state name (RARE)
            # TODO: log the error
            prompt = 'Enter STATE for `{}`:\t'.format(self.latlon)
            state = input(prompt).strip()

        self.state = state.lower()
