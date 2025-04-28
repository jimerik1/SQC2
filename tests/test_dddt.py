import unittest
import math
from services.qc.dddt import perform_dddt

class DDDTTests(unittest.TestCase):
    
    def setUp(self):
        # Create sample IPM data with depth error parameters
        self.ipm_data = {
            'error_terms': [
                {'name': 'DREF-PIPE', 'vector': 'e', 'tie_on': 's', 'value': 0.5, 'unit': 'm'},
                {'name': 'DREF-WIRE', 'vector': 'e', 'tie_on': 's', 'value': 0.3, 'unit': 'm'},
                {'name': 'DSF-PIPE', 'vector': 'e', 'tie_on': 's', 'value': 0.0003, 'unit': 'm/m'},
                {'name': 'DSF-WIRE', 'vector': 'e', 'tie_on': 's', 'value': 0.0002, 'unit': 'm/m'},
                {'name': 'DST-PIPE', 'vector': 'e', 'tie_on': 's', 'value': 0.00001, 'unit': 'm/m²'},
                {'name': 'DST-WIRE', 'vector': 'e', 'tie_on': 's', 'value': 0.00002, 'unit': 'm/m²'}
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
        
        # Patch the function in the dddt module
        import services.qc.dddt
        services.qc.dddt.get_error_term_value = mock_get_error_term_value
    
    def test_dddt_good_case(self):
        # Create depth measurements with small difference
        pipe_depth = 1000.0
        wireline_depth = 999.5
        survey = {
            'inclination': 30.0,
            'true_vertical_depth': 866.0  # 1000 * cos(30°)
        }
        
        result = perform_dddt(pipe_depth, wireline_depth, survey, self.ipm_data)
        
        # The difference of 0.5m should be within tolerance at this depth
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['measurements']['pipe_depth'], pipe_depth)
        self.assertEqual(result['measurements']['wireline_depth'], wireline_depth)
        self.assertEqual(result['errors']['depth_difference'], 0.5)
    
    def test_dddt_larger_depth(self):
        # Create depth measurements at a larger depth
        pipe_depth = 3000.0
        wireline_depth = 2998.0
        survey = {
            'inclination': 45.0,
            'true_vertical_depth': 2121.3  # 3000 * cos(45°)
        }
        
        result = perform_dddt(pipe_depth, wireline_depth, survey, self.ipm_data)
        
        # The difference of 2.0m at this larger depth should still be valid
        self.assertTrue(result['is_valid'])
    
    def test_dddt_invalid_case(self):
        # Create depth measurements with large difference
        pipe_depth = 1000.0
        wireline_depth = 995.0  # 5m difference
        survey = {
            'inclination': 30.0,
            'true_vertical_depth': 866.0
        }
        
        result = perform_dddt(pipe_depth, wireline_depth, survey, self.ipm_data)
        
        # The difference of 5.0m should be outside tolerance at this depth
        self.assertFalse(result['is_valid'])
    
    def test_dddt_with_tvd_calculation(self):
        # Test case where true vertical depth is not provided
        pipe_depth = 1000.0
        wireline_depth = 999.5
        survey = {
            'inclination': 30.0
            # No TVD provided, should be calculated
        }
        
        result = perform_dddt(pipe_depth, wireline_depth, survey, self.ipm_data)
        
        # Verify that TVD was calculated correctly
        self.assertAlmostEqual(result['details']['true_vertical_depth'], 866.0, delta=0.1)
        self.assertTrue(result['is_valid'])

if __name__ == '__main__':
    unittest.main()