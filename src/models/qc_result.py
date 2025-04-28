# models/qc_result.py
class QCResult:
    """Class representing the result of a QC test"""
    
    def __init__(self, test_name):
        self.test_name = test_name
        self.is_valid = False
        self.measurements = {}
        self.theoretical_values = {}
        self.errors = {}
        self.tolerances = {}
        self.details = {}
    
    def set_validity(self, is_valid):
        """Set the validity of the test result"""
        self.is_valid = is_valid
        return self
    
    def add_measurement(self, name, value):
        """Add a measurement value"""
        self.measurements[name] = value
        return self
    
    def add_theoretical(self, name, value):
        """Add a theoretical/expected value"""
        self.theoretical_values[name] = value
        return self
    
    def add_error(self, name, value):
        """Add an error (difference between measured and theoretical)"""
        self.errors[name] = value
        return self
    
    def add_tolerance(self, name, value):
        """Add a tolerance value"""
        self.tolerances[name] = value
        return self
    
    def add_detail(self, name, value):
        """Add a detail"""
        self.details[name] = value
        return self
    
    def to_dict(self):
        """Convert the result to a dictionary"""
        return {
            'test_name': self.test_name,
            'is_valid': self.is_valid,
            'measurements': self.measurements,
            'theoretical_values': self.theoretical_values,
            'errors': self.errors,
            'tolerances': self.tolerances,
            'details': self.details
        }