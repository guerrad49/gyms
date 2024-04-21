from geopy.geocoders import Nominatim


LONG_TERM_DEFENDING = 100   # in days


class Gym:
    '''A container to manage all gym-related fields'''
    
    def __init__(self, image_id: int):
        '''
        Parameters
        ----------
        image_id:
            The value identifying a gym with an image
        '''
        self.image = image_id
    

    def set_fields_from_image(self, data: dict):
        '''
        Helper method to set multiple gym fields.

        Parameters
        ----------
        data:
            The gym values extracted from image text
        '''

        self.set_title(data)
        self.set_victories(data)
        self.set_time_defended(data)
        self.set_treats(data)
        self.set_style()


    def set_title(self, d: dict):
        self.title = d['title']


    def set_victories(self, d: dict):
        self.victories = int(d['victories'])


    def set_time_defended(self, d: dict):
        '''Compute total time defended from time components'''

        # create formatted subset of dictionary
        subd = {k:d[k] for k in ['days','hours','minutes']}
        subd = {k:0 if v is None else int(v) for k,v in subd.items()}
        
        self.days    = subd['days']
        self.hours   = subd['hours']
        self.minutes = subd['minutes']
        
        total = self.days + self.hours / 24 + self.minutes / 1440
        self.defended = round(total, 4)


    def set_treats(self, d: dict):
        self.treats = int(d['treats'])


    def set_style(self):
        '''Determine style depending on time defended'''

        if self.days >= LONG_TERM_DEFENDING:
            self.style = '100+ days'
        else:
            self.style = 'gold'


    def set_location_fields(self, coordinates: str, email: str):
        '''Helper method to set all gym location fields'''
        
        self.set_address(coordinates, email)
        self.set_city()
        self.set_county()
        self.set_state()


    def set_address(self, coordinates: str, email: str):
        '''
        Set address dictionary using third party library.

        Parameters
        ----------
        coordinates:
            The known coordinates with `lat,long` format
        email:
            The user's email required by third party ToS
        '''

        self.coordinates  = coordinates
        geolocator        = Nominatim(user_agent=email)
        location          = geolocator.reverse(self.coordinates.split(','))
        self.address      = location.raw['address']   # dictionary


    def set_city(self):
        city = None

        # most common options
        for option in ['city','town','village','township']:
            if option in self.address.keys():
                city = self.address[option]
        
        # manually enter city name
        if city is None:
            prompt = 'Enter CITY for `{}`:\t'.format(self.coordinates)
            city   = input(prompt).strip()

        self.city = city.lower()


    def set_county(self):
        try:
            county = self.address['county']
        except KeyError:
            # manually enter county name
            prompt = 'Enter COUNTY for `{}`:\t'.format(self.coordinates)
            county = input(prompt).strip()
        
        county = county.lower()
        self.county = county.removesuffix(' county')


    def set_state(self):
        self.state = self.address['state'].lower()


    def format_fields(self) -> list:
        '''
        Construct custom list of attributes.
        
        Returns
        -------
        fields:
            The object's attribute values reorganized
        '''

        fields = [
            v for k,v in vars(self).items() 
            if k not in ['style', 'address']
            ]
        fields.insert(2, self.style)

        return fields
