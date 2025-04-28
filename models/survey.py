# models/survey.py
class Survey:
    """Class representing a directional survey measurement"""
    
    def __init__(self, data=None):
        # Basic survey data
        self.depth = 0.0
        self.inclination = 0.0  # uncorrected
        self.azimuth = 0.0  # uncorrected
        self.toolface = 0.0
        
        # Station location
        self.latitude = 0.0
        self.longitude = 0.0
        
        # Accelerometer readings
        self.Gx = 0.0
        self.Gy = 0.0
        self.Gz = 0.0
        
        # Gyro readings (for gyro tools)
        self.gyro_x = 0.0
        self.gyro_y = 0.0
        
        # Magnetometer readings (for magnetic tools)
        self.Bx = 0.0
        self.By = 0.0
        self.Bz = 0.0
        
        # Reference field data
        self.expected_geomagnetic_field = None
        self.expected_gravity_field_vector = None
        
        # If data is provided, parse it
        if data:
            self.parse_data(data)
    
    def parse_data(self, data):
        """Parse survey data from dictionary"""
        # Basic survey data
        self.depth = data.get('depth', 0.0)
        self.inclination = data.get('inclination', 0.0)
        self.azimuth = data.get('azimuth', 0.0)
        self.toolface = data.get('toolface', 0.0)
        
        # Station location
        self.latitude = data.get('latitude', 0.0)
        self.longitude = data.get('longitude', 0.0)
        
        # Accelerometer readings
        self.Gx = data.get('Gx', 0.0)
        self.Gy = data.get('Gy', 0.0)
        self.Gz = data.get('Gz', 0.0)
        
        # Gyro readings
        self.gyro_x = data.get('gyro_x', 0.0)
        self.gyro_y = data.get('gyro_y', 0.0)
        
        # Magnetometer readings
        self.Bx = data.get('Bx', 0.0)
        self.By = data.get('By', 0.0)
        self.Bz = data.get('Bz', 0.0)
        
        # Reference field data
        self.expected_geomagnetic_field = data.get('expected_geomagnetic_field', None)
        self.expected_gravity_field_vector = data.get('expected_gravity_field_vector', None)
    
    def to_dict(self):
        """Convert survey to dictionary"""
        return {
            'depth': self.depth,
            'inclination': self.inclination,
            'azimuth': self.azimuth,
            'toolface': self.toolface,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'Gx': self.Gx,
            'Gy': self.Gy,
            'Gz': self.Gz,
            'gyro_x': self.gyro_x,
            'gyro_y': self.gyro_y,
            'Bx': self.Bx,
            'By': self.By,
            'Bz': self.Bz,
            'expected_geomagnetic_field': self.expected_geomagnetic_field,
            'expected_gravity_field_vector': self.expected_gravity_field_vector
        }
    
    def get_accelerometer_vector(self):
        """Return the accelerometer vector as a tuple"""
        return (self.Gx, self.Gy, self.Gz)
    
    def get_magnetometer_vector(self):
        """Return the magnetometer vector as a tuple"""
        return (self.Bx, self.By, self.Bz)
    
    def get_gyro_vector(self):
        """Return the gyro vector as a tuple"""
        return (self.gyro_x, self.gyro_y)