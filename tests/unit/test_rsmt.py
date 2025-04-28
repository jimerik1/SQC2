import unittest
import math
import numpy as np
from services.qc.rsmt import perform_rsmt

class RSMTTests(unittest.TestCase):
    
    def setUp(self):
        # Create sample IPM data with misalignment parameters
        self.ipm_data = {
            'error_terms': [
                {'name': 'MX', 'vector': 'e', 'tie_on': 's', 'value': 0.1, 'unit': 'deg'},
                {'name': 'MY', 'vector': 'e', 'tie_on': 's', 'value': 0.1, 'unit': 'deg'}
            ]
        }
        
        # Create mock implementation of the get_error_term_value function
        def mock_get_error_term_value(ipm, name, vector='', tie_on=''):
            for term in ipm['error_terms']:
                if (term['name'] == name and
                    (not vector or term['vector'] == vector) and
                    (not tie_on or term['tie_on'] == tie_on)):
                    return term['value']
            return 0.0
        
        # Patch the function in the rsmt module
        import services.qc.rsmt
        services.qc.rsmt.get_error_term_value = mock_get_error_term_value
    
    def test_rsmt_good_case(self):
        # Create survey data with different toolfaces, no misalignment
        surveys = [
            {'inclination': 45.0, 'toolface': 0.0},
            {'inclination': 45.0, 'toolface': 90.0},
            {'inclination': 45.0, 'toolface': 180.0},
            {'inclination': 45.0, 'toolface': 270.0},
            {'inclination': 45.0, 'toolface': 45.0}
        ]
        
        result = perform_rsmt(surveys, self.ipm_data)
        
        self.assertTrue(result['is_valid'])
        self.assertAlmostEqual(result['measurements']['misalignment_mx'], 0.0, delta=0.01)
        self.assertAlmostEqual(result['measurements']['misalignment_my'], 0.0, delta=0.01)
    
    def test_rsmt_with_misalignment(self):
        # Create survey data with simulated misalignment (MX=0.2, MY=0.3)
        mx = 0.2
        my = 0.3
        ref_inc = 45.0
        ref_tf = 0.0
        
        # Function to calculate inclination based on toolface and misalignment
        def calculate_inclination(toolface, ref_inc, ref_tf, mx, my):
            tf_rad = math.radians(toolface)
            ref_tf_rad = math.radians(ref_tf)
            
            # Inclination difference due to misalignment
            inc_diff = mx * (math.cos(tf_rad) - math.cos(ref_tf_rad)) + \
                      my * (math.sin(tf_rad) - math.sin(ref_tf_rad))
            
            return ref_inc + inc_diff
        
        surveys = [
            {'inclination': ref_inc, 'toolface': ref_tf},
            {'inclination': calculate_inclination(90.0, ref_inc, ref_tf, mx, my), 'toolface': 90.0},
            {'inclination': calculate_inclination(180.0, ref_inc, ref_tf, mx, my), 'toolface': 180.0},
            {'inclination': calculate_inclination(270.0, ref_inc, ref_tf, mx, my), 'toolface': 270.0},
            {'inclination': calculate_inclination(45.0, ref_inc, ref_tf, mx, my), 'toolface': 45.0}
        ]
        
        result = perform_rsmt(surveys, self.ipm_data)
        
        # Expect the test to fail because MX=0.2 is outside the tolerance (3 * 0.1 = 0.3)
        self.assertFalse(result['is_valid'])
        self.assertAlmostEqual(result['measurements']['misalignment_mx'], mx, delta=0.01)
        self.assertAlmostEqual(result['measurements']['misalignment_my'], my, delta=0.01)
    
    def test_rsmt_insufficient_toolface_variation(self):
        # Create survey data with insufficient toolface variation
        surveys = [
            {'inclination': 45.0, 'toolface': 0.0},
            {'inclination': 45.0, 'toolface': 10.0},
            {'inclination': 45.0, 'toolface': 20.0},
            {'inclination': 45.0, 'toolface': 30.0},
            {'inclination': 45.0, 'toolface': 40.0}
        ]
        
        result = perform_rsmt(surveys, self.ipm_data)
        
        self.assertFalse(result['is_valid'])
        self.assertIn('error', result)  # Should have an error message
        
    def test_rsmt_too_few_measurements(self):
        # Create survey data with too few measurements
        surveys = [
            {'inclination': 45.0, 'toolface': 0.0},
            {'inclination': 45.0, 'toolface': 90.0},
            {'inclination': 45.0, 'toolface': 180.0}
        ]
        
        result = perform_rsmt(surveys, self.ipm_data)
        
        self.assertFalse(result['is_valid'])
        self.assertIn('error', result)  # Should have an error message
    
    def test_rsmt_near_vertical(self):
        # Create survey data with inclination too low
        surveys = [
            {'inclination': 2.0, 'toolface': 0.0},
            {'inclination': 2.0, 'toolface': 90.0},
            {'inclination': 2.0, 'toolface': 180.0},
            {'inclination': 2.0, 'toolface': 270.0},
            {'inclination': 2.0, 'toolface': 45.0}
        ]
        
        result = perform_rsmt(surveys, self.ipm_data)
        
        self.assertFalse(result['is_valid'])
        self.assertIn('error', result)  # Should have an error message

if __name__ == '__main__':
    unittest.main()