"""
PokemonGo.gym
-------------

This module contains GoldGym class for compiling a gym's 
data in one location such as:
    1. Initial known gym values from database
    2. Values read using PokemonGo.BadgeImage class
    3. Methods which complete gym location values

Once all gym values are set, the best use-case is to pass
a GoldGym object to the `write_row` method of 
PokemonGo.GoogleSheet class.

It is also recommended the use of setter class methods 
for safe-handling of class attributes.
"""


from typing import Optional, Any

from geopy.geocoders import Nominatim


HRS_IN_DAY  = 24
MINS_IN_DAY = 1440
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
    ...     title='sydney opera house', model='i15', 
    ...     victories=100, days=10, hours=7,
    ...     minutes=20, treats=500)
    >>> 
    >>> # instance w/ unpacking dictionary of parameters
    >>> params = {
    ...     'title': '大阪城', model='i11', 'victories': 246, 
    ...     'days': 2, 'hours': 3, 'minutes': 40, 'treats': 369
    ...     }
    >>> cc = GoldGym(uid=3, **params)
    """
    
    def __init__(
        self, 
        uid:       int,
        title:     Optional[str] = None,
        model:     Optional[str] = None,
        victories: Optional[int] = 0,
        days:      Optional[int] = 0,
        hours:     Optional[int] = 0,
        minutes:   Optional[int] = 0,
        treats:    Optional[int] = 0
        ) -> None:
        self.uid       = self._checkint(uid)
        self.title     = title
        self.model     = model
        self.style     = None
        self.victories = self._checkint(victories)
        self.days      = self._checkint(days)
        self.hours     = self._checkint(hours)
        self.minutes   = self._checkint(minutes)
        self.defended  = 0
        self.treats    = self._checkint(treats)
        self.errors    = list()
        
        """
        Parameters
        ----------
        uid:
            The unique id number identifying a gym
        title:
            The gym title
        model:
            The phone-source model
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
        errors:
            The list of processing errors
        """
    
    def _checkint(self, x: Any) -> int:
        """Check argument type for <int>."""

        if not isinstance(x, int):
            errMsg = 'argument "{}" must be <int> type'.format(x)
            raise TypeError(errMsg)
        return x
    

    def set_victories(self, x: int) -> None:
        """Safe setting function for victories."""

        self.victories = self._checkint(x)
    

    def set_days(self, x: int) -> None:
        """Safe setting function for days."""
        
        self.days = self._checkint(x)
    

    def set_hours(self, x: int) -> None:
        """Safe setting function for hours."""

        self.hours = self._checkint(x)
    

    def set_minutes(self, x: int) -> None:
        """Safe setting function for minutes."""
        
        self.minutes = self._checkint(x)
    

    def set_treats(self, x: int) -> None:
        """Safe setting function for treats."""
        
        self.treats = self._checkint(x)


    def set_time_defended(self) -> None:
        """
        Compute total time defended from time attributes. 
        Default is 0.

        Exceptions
        ----------
        AttributeError if missing required attributes
        """

        total = self.days + self.hours / HRS_IN_DAY \
            + self.minutes / MINS_IN_DAY

        self.defended = round(total, 4)   # in days


    def set_style(self) -> None:
        """
        Determine gym style based on number of days defended.

        Exceptions
        ----------
        AttributeError if missing 'days' attribute
        """

        if self.days < LONG_TERM_DEFENDING:
            self.style = 'gold'
        else:
            self.style = '100+ days'


    def set_address(self, latlon: str, email: str) -> None:
        """
        Set address dictionary.

        Parameters
        ----------
        latlon:
            The known coordinates in `lat,long` format
        email:
            The user's email required by third party ToS
        
        See Also
        --------
        geopy.geocoders.Nominatim
        """

        self.latlon = latlon
        geolocator  = Nominatim(user_agent=email)

        # proactive format clean up
        coords_list = [x.strip() for x in self.latlon.split(',')]

        location     = geolocator.reverse(coords_list)
        self.address = location.raw['address']   # dictionary


    def set_city(self) -> None:
        """
        Set the gym's city from address.
        Note: May require user interface.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError is missing 'address' attribute
        """

        city = None

        # common options address dictionary
        for option in ['city','town','village','township']:
            if option in self.address.keys():
                city = self.address[option]
        
        if not city:
            self.errors.append('CITY')
            # manually enter city name
            prompt = 'Enter CITY for `{}`:\t'.format(self.latlon)
            city   = input(prompt).strip()

        self.city = city.lower()


    def set_county(self) -> None:
        """
        Set the gym's county from address.
        Note: May require user interface.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError if missing 'address' attribute
        """

        try:
            county = self.address['county']
        except KeyError:
            self.errors.append('COUNTY')
            # manually enter county name
            prompt = 'Enter COUNTY for `{}`:\t'.format(self.latlon)
            county = input(prompt).strip()
        
        county = county.lower()
        self.county = county.removesuffix(' county')


    def set_state(self) -> None:
        """
        Set the gym's state from address.
        Note: May require user interface.
        
        Required
        --------
        GoldGym.set_address

        Exceptions
        ----------
        AttributeError if missing 'address' attribute
        """

        try:
           state = self.address['state']
        except KeyError:
            self.errors.append('STATE')
            # manually enter state name (RARE)
            prompt = 'Enter STATE for `{}`:\t'.format(self.latlon)
            state = input(prompt).strip()

        self.state = state.lower()
