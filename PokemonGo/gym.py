"""
PokemonGo.gym
"""

from typing import Optional, Any

from geopy.geocoders import Nominatim
from .exceptions import ArgumentError


HRS_IN_DAY = 24
MINS_IN_DAY = 1400
LONG_TERM_DEFENDING = 100   # in days


class GoldGym:
    """
    An instance of this class represents a container for 
    managing gym-related information.
    """
    
    def __init__(
        self, 
        uid:       int | str,
        title:     Optional[str] = None,
        victories: Optional[int | str] = 0,
        days:      Optional[int | str] = 0,
        hours:     Optional[int | str] = 0,
        minutes:   Optional[int | str] = 0,
        treats:    Optional[int | str] = 0
    ) -> None:
        self.uid       = self._int(uid)
        self.title     = title
        self.style     = None
        self.victories = self._int(victories)
        self.days      = self._int(days)
        self.hours     = self._int(hours)
        self.minutes   = self._int(minutes)
        self.defended  = 0
        self.treats    = self._int(treats)
        
        """
        Parameters
        ----------
        uid:
            The unique id number relating an image to a gym
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


    def _int(self, x: Any) -> int:
        """Convert argument to int when possible."""

        # attempt str -> int
        if isinstance(x, str):
            try:
                int(x)
            except ValueError:
                raise ArgumentError
            else:
                return int(x)
            
        if not isinstance(x, int):
            raise ArgumentError

        return x
    

    def set_defended(self) -> None:
        """
        Compute total time defended from time attributes. 
        User should ensure time attributes have been set. 
        Otherwise, time defended will be 0.
        """

        total = self.days + self.hours / HRS_IN_DAY \
            + self.minutes / MINS_IN_DAY

        self.defended = round(total, 4)   # in days


    def set_style(self) -> None:
        """
        Determine gym style based on number of days defended. 
        Default is `gold` style.
        """

        if self.days >= LONG_TERM_DEFENDING:
            self.style = '100+ days'
        else:
            self.style = 'gold'


    def set_address(self, coordinates: str, email: str) -> None:
        """
        Set address dictionary.

        Parameters
        ----------
        coordinates:
            The known coordinates in `lat,long` format
        email:
            The user's email required by third party ToS
        """

        self.coordinates  = coordinates
        geolocator        = Nominatim(user_agent=email)

        # proactive format clean up
        coords_list  = [x.strip() for x in self.coordinates.split(',')]

        location     = geolocator.reverse(coords_list)
        self.address = location.raw['address']   # dictionary


    def set_city(self) -> None:
        """Set the gym's city from address"""

        if 'address' not in vars(self):
            raise AttributeError('address was not set')

        city = None

        # most common options
        for option in ['city','town','village','township']:
            if option in self.address.keys():
                city = self.address[option]
        
        # manually enter city name
        # TODO: log the error
        if not city:
            prompt = 'Enter CITY for `{}`:\t'.format(self.coordinates)
            city   = input(prompt).strip()

        self.city = city.lower()


    def set_county(self) -> None:
        """Set the gym's county from address"""

        try:
            county = self.address['county']
        except AttributeError:
            raise AttributeError('address was not set')
        except KeyError:
            # manually enter county name
            # TODO: log the error
            prompt = 'Enter COUNTY for `{}`:\t'.format(self.coordinates)
            county = input(prompt).strip()
        
        county = county.lower()
        self.county = county.removesuffix(' county')


    def set_state(self) -> None:
        """Set the gym's state from address"""
        try:
           state = self.address['state']
        except AttributeError:
            raise AttributeError('address was not set')
        except KeyError:
            # manually enter state name (RARE)
            # TODO: log the error
            prompt = 'Enter STATE for `{}`:\t'.format(self.coordinates)
            state = input(prompt).strip()

        self.state = state.lower()


    def values(self) -> list:
        """
        Returns
        -------
        fields:
            The object's attribute values w/o address
        """

        fields = [
            v for k,v in vars(self).items() 
            if k not in ['address']
            ]

        return fields
