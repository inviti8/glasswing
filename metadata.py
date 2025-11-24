from nicegui.binding import BindableProperty
from nicegui import binding, app
from dataclasses import field

@binding.bindable_dataclass
class IPTC:
    # Basic IPTC fields
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
    
    # Data Mining Fields (IPTC Extension 1.8+)
    use_data_mining: bool = False
    data_mining: str = 'DMI-PROHIBITED'
    data_mining_options: list = field(default_factory=lambda: [
        'DMI-PROHIBITED',
        'DMI-PROHIBITED-AIMLTRAINING',
        'DMI-PROHIBITED-GENAIMLTRAINING',
        'DMI-PROHIBITED-EXCEPTSEARCHENGINEINDEXING',
        'DMI-ALLOWED',
        'DMI-UNSPECIFIED'
    ])
    use_other_constraints: bool = False
    other_constraints: str = ''

    # Field mapping to ExifTool tags
    FIELD_MAPPING = {
        'objectname': 'IPTC:ObjectName',
        'caption_abstract': 'IPTC:Caption-Abstract',
        'keywords': 'IPTC:Keywords',
        'credit_line': 'IPTC:Credit',
        'copyright_notice': 'IPTC:CopyrightNotice',
        'byline': 'IPTC:By-line',
        'city': 'IPTC:City',
        'country': 'IPTC:Country-PrimaryLocationName',
        'destination': 'IPTC:Destination',
        'data_mining': 'XMP-plus:DataMining',
        'other_constraints': 'XMP-plus:OtherConstraints'
    }

    def init(self):
        """Initialize the IPTC object with default or stored values."""
        self.data_mining = app.storage.user.get('iptc_data.data_mining', 'DMI-PROHIBITED')
        self.other_constraints = app.storage.user.get('iptc_data.other_constraints', '')

    def get_data_mining_options(self):
        """Return the list of available data mining options."""
        return self.data_mining_options

    def set_data_mining(self, value):
        """Set the data mining value and update storage."""
        if value in self.data_mining_options:
            self.data_mining = value
            self.use_data_mining = True
            app.storage.user['iptc_data.data_mining'] = self.data_mining
            app.storage.user['iptc_data.use_data_mining'] = self.use_data_mining

    def set_other_constraints(self, value):
        """Set other constraints and update storage."""
        self.other_constraints = value
        self.use_other_constraints = bool(value)
        app.storage.user['iptc_data.other_constraints'] = self.other_constraints
        app.storage.user['iptc_data.use_other_constraints'] = self.use_other_constraints

    def get_storage_field(self, field_name):
        """Map display field names to internal attribute names."""
        field_map = {
            'Object Name': 'objectname',
            'Caption/Abstract': 'caption_abstract',
            'Keywords': 'keywords',
            'Credit Line': 'credit_line',
            'CopyrightNotice': 'copyright_notice',
            'Copyright Notice': 'copyright_notice',
            'By-line': 'byline',
            'City': 'city',
            'Country': 'country',
            'Destination': 'destination',
            'Data Mining': 'data_mining',
            'Other Constraints': 'other_constraints'
        }
        return f'iptc_data.{field_map.get(field_name, field_name.lower().replace(" ", "_"))}'

    def init_storage(self):
        """Initialize storage with default values."""
        storage_map = {
            # Basic fields
            'use_objectname': self.use_objectname,
            'objectname': self.objectname,
            'use_caption_abstract': self.use_caption_abstract,
            'caption_abstract': self.caption_abstract,
            'use_keywords': self.use_keywords,
            'keywords': self.keywords,
            'use_credit_line': self.use_credit_line,
            'credit_line': self.credit_line,
            'use_copyright_notice': self.use_copyright_notice,
            'copyright_notice': self.copyright_notice,
            'use_byline': self.use_byline,
            'byline': self.byline,
            'use_city': self.use_city,
            'city': self.city,
            'use_country': self.use_country,
            'country': self.country,
            'use_destination': self.use_destination,
            'destination': self.destination,
            # Data mining fields
            'use_data_mining': self.use_data_mining,
            'data_mining': self.data_mining,
            'use_other_constraints': self.use_other_constraints,
            'other_constraints': self.other_constraints
        }
        
        for key, value in storage_map.items():
            app.storage.user[f'iptc_data.{key}'] = value

    def update_from_storage(self):
        """Update object attributes from storage."""
        storage = app.storage.user
        prefix = 'iptc_data.'
        
        # Update boolean flags
        for field in ['use_objectname', 'use_caption_abstract', 'use_keywords',
                     'use_credit_line', 'use_copyright_notice', 'use_byline',
                     'use_city', 'use_country', 'use_destination', 
                     'use_data_mining', 'use_other_constraints']:
            if prefix + field in storage:
                setattr(self, field, storage[prefix + field])
        
        # Update string fields
        for field in ['objectname', 'caption_abstract', 'keywords', 'credit_line',
                     'copyright_notice', 'byline', 'city', 'country', 'destination',
                     'data_mining', 'other_constraints']:
            if prefix + field in storage:
                setattr(self, field, storage[prefix + field])

    def to_dict(self):
        """Convert the IPTC object to a dictionary."""
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
            'use_other_constraints': self.use_other_constraints,
            
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
            'Other Constraints': self.other_constraints
        }

    def keywords_array(self):
        """Split keywords string into an array."""
        return [k.strip() for k in self.keywords.split(',') if k.strip()]
        
    @classmethod
    def from_dict(cls, data):
        """Create an IPTC instance from a dictionary."""
        instance = cls()
        
        # Update boolean flags
        for field in ['use_objectname', 'use_caption_abstract', 'use_keywords',
                     'use_credit_line', 'use_copyright_notice', 'use_byline',
                     'use_city', 'use_country', 'use_destination', 
                     'use_data_mining', 'use_other_constraints']:
            if field in data:
                setattr(instance, field, bool(data[field]))
                
        # Update string fields
        for field in ['objectname', 'caption_abstract', 'keywords', 'credit_line',
                     'copyright_notice', 'byline', 'city', 'country', 'destination',
                     'data_mining', 'other_constraints']:
            if field in data:
                setattr(instance, field, str(data[field]))
                
        # Handle data mining value
        if 'data_mining' in data:
            instance.set_data_mining(data['data_mining'])
            
        return instance

    def to_exif_dict(self):
        """Convert to a dictionary with ExifTool-compatible field names."""
        result = {}
        
        # Handle standard IPTC fields
        for field in ['objectname', 'caption_abstract', 'keywords', 'credit_line', 
                     'copyright_notice', 'byline', 'city', 'country', 'destination',
                     'data_mining', 'other_constraints']:
            use_flag = getattr(self, f'use_{field}', False)
            field_value = getattr(self, field, '')
            
            # Only include the field if its use flag is True and it has a non-empty value
            if use_flag and field_value:
                # Special handling for keywords - split into list if it's a comma-separated string
                if field == 'keywords' and ',' in field_value:
                    result[self.FIELD_MAPPING[field]] = [k.strip() for k in field_value.split(',') if k.strip()]
                else:
                    result[self.FIELD_MAPPING[field]] = field_value
        
        return result

    @classmethod
    def from_exif_dict(cls, exif_data):
        """Create an IPTC instance from ExifTool output."""
        instance = cls()
        reverse_mapping = {v: k for k, v in cls.FIELD_MAPPING.items()}
        
        for exif_field, value in exif_data.items():
            if exif_field in reverse_mapping:
                field = reverse_mapping[exif_field]
                if field in ['data_mining', 'other_constraints']:
                    setattr(instance, field, str(value))
                    setattr(instance, f'use_{field}', True)
                    
        return instance