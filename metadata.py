from nicegui.binding import BindableProperty
from nicegui import binding, app

@binding.bindable_dataclass
class IPTC:
    use_objectname: bool = False
    objectname: str = ''
    use_caption_abstract: bool = False
    caption_abstract: str = ''
    use_keywords: bool = False
    keywords: str = ''
    use_credit_line: bool = False
    credit_line: str = ''
    use_copyright_notice: bool = False
    copyright_notice: str = 'All Rights Reserved'
    use_byline: bool = False
    byline: str = ''
    use_city: bool = False
    city: str = ''
    use_country: bool = False
    country: str = ''
    use_destination: bool = False
    destination: str = ''
    use_data_mining: bool = False
    data_mining: str = 'DMI-PROHIBITED'
    data_mining_array: str = 'DMI-PROHIBITED,DMI-PROHIBITED-AIMLTRAINING,DMI-PROHIBITED-GENAIMLTRAINING,DMI-PROHIBITED-EXCEPTSEARCHENGINEINDEXING,DMI-ALLOWED,DMI-UNSPECIFIED'

    def init(self):
        self.data_mining = app.storage.user.get('iptc_data.data_mining', 'DMI-PROHIBITED')

    def get_data_mining_array(self):
        return self.data_mining_array.split(',')

    def set_data_mining(self, value):
        self.data_mining = value
        arr = self.get_data_mining_array()
        if value in arr:
            arr.remove(value)
            arr.insert(0, value)
            self.data_mining_array = ','.join(arr)
        self.use_data_mining = True
        app.storage.user['iptc_data.use_data_mining'] = self.use_data_mining
        app.storage.user['iptc_data.data_mining'] = self.data_mining

    def get_storage_field(self, field_name):
        if field_name == 'Object Name':
            field_name = 'objectname'
        elif field_name == 'Caption/Abstract':
            field_name = 'caption_abstract'
        elif field_name == 'Keywords':
            field_name = 'keywords'
        elif field_name == 'Credit Line':
            field_name = 'credit_line'
        elif field_name == 'CopyrightNotice':
            field_name = 'copyright_notice'
        elif field_name == 'Copyright Notice':
            field_name = 'copyright_notice'
        elif field_name == 'By-line':
            field_name = 'byline'
        elif field_name == 'City':
            field_name = 'city'
        elif field_name == 'Country':
            field_name = 'country'
        elif field_name == 'Destination':
            field_name = 'destination'
        elif field_name == 'Data Mining':
            field_name = 'data_mining'
        elif field_name == 'Data Mining Array':
            field_name = 'data_mining_array'
        elif field_name == 'SpecialInstructions':
            field_name = 'data_mining'
        return f'iptc_data.{field_name}'

    def init_storage(self):
        app.storage.user['iptc_data.use_objectname'] = self.use_objectname
        app.storage.user['iptc_data.objectname'] = self.objectname
        app.storage.user['iptc_data.use_caption_abstract'] = self.use_caption_abstract
        app.storage.user['iptc_data.caption_abstract'] = self.caption_abstract
        app.storage.user['iptc_data.use_keywords'] = self.use_keywords
        app.storage.user['iptc_data.keywords'] = self.keywords
        app.storage.user['iptc_data.use_credit_line'] = self.use_credit_line
        app.storage.user['iptc_data.credit_line'] = self.credit_line
        app.storage.user['iptc_data.use_copyright_notice'] = self.use_copyright_notice
        app.storage.user['iptc_data.copyright_notice'] = self.copyright_notice
        app.storage.user['iptc_data.use_byline'] = self.use_byline
        app.storage.user['iptc_data.byline'] = self.byline
        app.storage.user['iptc_data.use_city'] = self.use_city
        app.storage.user['iptc_data.city'] = self.city
        app.storage.user['iptc_data.use_country'] = self.use_country
        app.storage.user['iptc_data.country'] = self.country
        app.storage.user['iptc_data.use_destination'] = self.use_destination
        app.storage.user['iptc_data.destination'] = self.destination
        app.storage.user['iptc_data.use_data_mining'] = self.use_data_mining
        app.storage.user['iptc_data.data_mining'] = self.data_mining
        app.storage.user['iptc_data.data_mining_array'] = self.data_mining_array

    def update_from_storage(self):
        self.use_objectname = app.storage.user.get('iptc_data.use_objectname', False)
        self.objectname = app.storage.user.get('iptc_data.objectname', '')
        self.use_caption_abstract = app.storage.user.get('iptc_data.use_caption_abstract', False)
        self.caption_abstract = app.storage.user.get('iptc_data.caption_abstract', '')
        self.use_keywords = app.storage.user.get('iptc_data.use_keywords', False)
        self.keywords = app.storage.user.get('iptc_data.keywords', '')
        self.use_credit_line = app.storage.user.get('iptc_data.use_credit_line', False)
        self.credit_line = app.storage.user.get('iptc_data.credit_line', '')
        self.use_copyright_notice = app.storage.user.get('iptc_data.use_copyright_notice', False)
        self.copyright_notice = app.storage.user.get('iptc_data.copyright_notice', 'All Rights Reserved')
        self.use_byline = app.storage.user.get('iptc_data.use_byline', False)
        self.byline = app.storage.user.get('iptc_data.byline', '')
        self.use_city = app.storage.user.get('iptc_data.use_city', False)
        self.city = app.storage.user.get('iptc_data.city', '')
        self.use_country = app.storage.user.get('iptc_data.use_country', False)
        self.country = app.storage.user.get('iptc_data.country', '')
        self.use_destination = app.storage.user.get('iptc_data.use_destination', False)
        self.destination = app.storage.user.get('iptc_data.destination', '')
        self.use_data_mining = app.storage.user.get('iptc_data.use_data_mining', False)
        self.data_mining = app.storage.user.get('iptc_data.data_mining', 'DMI-PROHIBITED')
        self.data_mining_array = app.storage.user.get('iptc_data.data_mining_array', 'DMI-PROHIBITED,DMI-PROHIBITED-AIMLTRAINING,DMI-PROHIBITED-GENAIMLTRAINING,DMI-PROHIBITED-EXCEPTSEARCHENGINEINDEXING,DMI-ALLOWED,DMI-UNSPECIFIED')
        
    def to_dict(self):
        """Return a dictionary representation of the IPTC data."""
        return {
            # Boolean flags
            'use_objectname': self.use_objectname,
            'use_caption_abstract': self.use_caption_abstract,
            'use_keywords': self.use_keywords,
            'use_credit_line': self.use_credit_line,
            'use_copyright_notice': self.use_copyright_notice,
            'use_byline': self.use_byline,
            'use_city': self.use_city,
            'use_country': self.use_country,
            'use_destination': self.use_destination,
            'use_data_mining': self.use_data_mining,
            
            # String fields
            'Object Name': self.objectname,
            'Caption/Abstract': self.caption_abstract,
            'Keywords': self.keywords,
            'Credit Line': self.credit_line,
            'Copyright Notice': self.copyright_notice,
            'By-line': self.byline,
            'City': self.city,
            'Country': self.country,
            'Destination': self.destination,
            'Data Mining': self.data_mining,
            'Data Mining Array': self.data_mining_array
        }

    def keywords_array(self):
        return self.keywords.split(',')
        
    @classmethod
    def from_dict(cls, data):
        instance = cls()
        
        # Update boolean flags
        for field in ['use_objectname', 'use_caption_abstract', 'use_keywords',
                     'use_credit_line', 'use_copyright_notice', 'use_byline',
                     'use_city', 'use_country', 'use_destination', 'use_data_mining']:
            if field in data:
                setattr(instance, field, bool(data[field]))
                
        # Update string fields
        for field in ['objectname', 'caption_abstract', 'keywords', 'credit_line',
                     'copyright_notice', 'byline', 'city', 'country', 'destination',
                     'data_mining', 'data_mining_array']:
            if field in data:
                setattr(instance, field, str(data[field]))
                
        # If data_mining is set, ensure it's properly reflected in data_mining_array
        if 'data_mining' in data and hasattr(instance, 'data_mining_array'):
            instance.set_data_mining(data['data_mining'])
            
        return instance