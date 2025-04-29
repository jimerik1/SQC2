# models/qc_result.py

import numpy as np

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
        """Convert the result to a dictionary with Python native types"""
        # Helper function to convert numpy types to Python native types
        def convert_numpy(obj):
            if isinstance(obj, (np.integer, np.int32, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.ndarray, list)):
                return [convert_numpy(i) for i in obj]
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            else:
                return obj
        
        # Convert all values to Python native types
        return {
            'test_name': self.test_name,
            'is_valid': bool(self.is_valid),  # Ensure it's a Python boolean
            'measurements': convert_numpy(self.measurements),
            'theoretical_values': convert_numpy(self.theoretical_values),
            'errors': convert_numpy(self.errors),
            'tolerances': convert_numpy(self.tolerances),
            'details': convert_numpy(self.details)
        }