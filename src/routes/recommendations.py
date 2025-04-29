# Create a new file src/routes/recommendations.py

from flask import Blueprint, request, jsonify

recommendations_bp = Blueprint('recommendations', __name__)

@recommendations_bp.route('/recommend-tests', methods=['POST'])
def recommend_tests():
    """Recommend tests for a specific survey station based on inputs"""
    data = request.get_json()
    
    # Extract input parameters
    tool_type = data.get('tool_type', '')  # MWD, Gyro, Other
    current_station = data.get('current_station', {})
    current_survey = data.get('current_survey', [])
    overlaps_previous_run = data.get('overlaps_previous_run', False)
    is_first_station = data.get('is_first_station', False)
    is_in_run_out_run_available = data.get('is_in_run_out_run_available', False)
    is_bha_mounted = data.get('is_bha_mounted', False)
    is_constant_toolface = data.get('is_constant_toolface', False)
    has_ccl = data.get('has_ccl', False)
    is_in_drillpipe = data.get('is_in_drillpipe', False)
    
    # Initialize recommendations
    recommended_tests = []
    not_recommended_tests = []
    uncontrolled_error_terms = []
    
    # Define all available tests
    all_tests = [
        {"id": "get", "name": "Gravity Error Test"},
        {"id": "tfdt", "name": "Total Field + Dip Test"},
        {"id": "hert", "name": "Horizontal Earth Rate Test"},
        {"id": "rsmt", "name": "Rotation-Shot Misalignment Test"},
        {"id": "dddt", "name": "Dual Depth Difference Test"},
        {"id": "msat", "name": "Multi-Station Accelerometer Test"},
        {"id": "msgt", "name": "Multi-Station Gyro Test"},
        {"id": "msmt", "name": "Multi-Station Magnetometer Test"},
        {"id": "mse", "name": "Multi-Station Estimation"},
        {"id": "iomt", "name": "In-Run/Out-Run Misalignment Test"},
        {"id": "cadt", "name": "Continuous Azimuth Drift Test"},
        {"id": "idt", "name": "Inclination Difference Test"},
        {"id": "adt", "name": "Azimuth Difference Test"},
        {"id": "codt", "name": "Co-ordinate Difference Test"}
    ]
    
    # 1. Basic checks for all survey types - ALWAYS run these
    if tool_type.lower() == 'mwd':
        recommended_tests.append({
            'id': 'get',
            'name': 'Gravity Error Test',
            'priority': 'high',
            'reason': 'Basic verification of accelerometer integrity'
        })
        recommended_tests.append({
            'id': 'tfdt',
            'name': 'Total Field + Dip Test',
            'priority': 'high',
            'reason': 'Basic verification of magnetometer integrity'
        })
        
        # HERT is not applicable for MWD
        not_recommended_tests.append({
            'id': 'hert',
            'name': 'Horizontal Earth Rate Test',
            'reason': 'Not applicable for MWD tools that do not have gyroscopes'
        })
        
        uncontrolled_error_terms.extend(['sag', 'misalignments', 'declination', 'depth terms'])
        
    elif tool_type.lower() == 'gyro':
        recommended_tests.append({
            'id': 'get',
            'name': 'Gravity Error Test',
            'priority': 'high',
            'reason': 'Basic verification of accelerometer integrity'
        })
        recommended_tests.append({
            'id': 'hert',
            'name': 'Horizontal Earth Rate Test',
            'priority': 'high',
            'reason': 'Basic verification of gyroscope integrity'
        })
        
        # TFDT is not applicable for gyro
        not_recommended_tests.append({
            'id': 'tfdt',
            'name': 'Total Field + Dip Test',
            'reason': 'Not applicable for gyro tools that do not have magnetometers'
        })
        
        uncontrolled_error_terms.extend(['sag', 'misalignments', 'depth terms'])
    
    # 2. If we have multiple stations in the current survey, recommend multi-station tests
    if len(current_survey) >= 10:
        if tool_type.lower() == 'mwd':
            recommended_tests.append({
                'id': 'msat',
                'name': 'Multi-Station Accelerometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze accelerometer errors'
            })
            recommended_tests.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze magnetometer errors'
            })
            
            # MSGT is not applicable for MWD
            not_recommended_tests.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Not applicable for MWD tools that do not have gyroscopes'
            })
            
            # If really complex, recommend MSE
            if len(current_survey) >= 15:
                recommended_tests.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'priority': 'low',
                    'reason': 'Comprehensive error analysis possible with sufficient stations'
                })
            else:
                not_recommended_tests.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
                })
            
            # Remove these terms from uncontrolled since we're controlling them with multi-station tests
            if 'misalignments' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('misalignments')
                
        elif tool_type.lower() == 'gyro':
            recommended_tests.append({
                'id': 'msat',
                'name': 'Multi-Station Accelerometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze accelerometer errors'
            })
            recommended_tests.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze gyro errors'
            })
            
            # MSMT is not applicable for gyro
            not_recommended_tests.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Not applicable for gyro tools that do not have magnetometers'
            })
            
            # MSE is usually not needed for gyro but can be used
            if len(current_survey) >= 15:
                recommended_tests.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'priority': 'low',
                    'reason': 'Comprehensive error analysis possible with sufficient stations'
                })
            else:
                not_recommended_tests.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
                })
            
            # Remove these terms from uncontrolled since we're controlling them with multi-station tests
            if 'misalignments' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('misalignments')
    else:
        # Not enough stations for multi-station tests
        not_recommended_tests.append({
            'id': 'msat',
            'name': 'Multi-Station Accelerometer Test',
            'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
        })
        
        if tool_type.lower() == 'mwd':
            not_recommended_tests.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
            })
            not_recommended_tests.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Not applicable for MWD tools that do not have gyroscopes'
            })
        elif tool_type.lower() == 'gyro':
            not_recommended_tests.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
            })
            not_recommended_tests.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Not applicable for gyro tools that do not have magnetometers'
            })
        
        not_recommended_tests.append({
            'id': 'mse',
            'name': 'Multi-Station Estimation',
            'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
        })
    
    # 3. For BHA-mounted tools, recommend rotation shot tests
    if is_bha_mounted and not is_constant_toolface:
        recommended_tests.append({
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'priority': 'medium',
            'reason': 'BHA-mounted tool with variable toolface allows misalignment control'
        })
        # Remove misalignments from uncontrolled since RSMT will control them
        if 'misalignments' in uncontrolled_error_terms:
            uncontrolled_error_terms.remove('misalignments')
    else:
        not_recommended_tests.append({
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'reason': 'Not applicable for tools that are not BHA-mounted or have constant toolface'
        })
    
    # 4. For wireline surveys with CCL, recommend DDDT
    if has_ccl and is_in_drillpipe:
        recommended_tests.append({
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'priority': 'medium',
            'reason': 'CCL and drillpipe depths available for comparison'
        })
        # Remove depth terms from uncontrolled
        if 'depth terms' in uncontrolled_error_terms:
            uncontrolled_error_terms.remove('depth terms')
    else:
        not_recommended_tests.append({
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'reason': 'Not applicable without CCL in drillpipe (requires two independent depth measurements)'
        })
    
    # 5. For surveys with in-run/out-run data (continuous gyro)
    if is_in_run_out_run_available:
        recommended_tests.append({
            'id': 'iomt',
            'name': 'In-Run/Out-Run Misalignment Test',
            'priority': 'high',
            'reason': 'In-run/out-run data available for misalignment control'
        })
        recommended_tests.append({
            'id': 'cadt',
            'name': 'Continuous Azimuth Drift Test',
            'priority': 'high',
            'reason': 'In-run/out-run data available for drift control'
        })
        # Remove misalignments from uncontrolled since IOMT will control them
        if 'misalignments' in uncontrolled_error_terms:
            uncontrolled_error_terms.remove('misalignments')
    else:
        not_recommended_tests.append({
            'id': 'iomt',
            'name': 'In-Run/Out-Run Misalignment Test',
            'reason': 'Not applicable without in-run/out-run data'
        })
        not_recommended_tests.append({
            'id': 'cadt',
            'name': 'Continuous Azimuth Drift Test',
            'reason': 'Not applicable without in-run/out-run data'
        })
    
    # 6. If overlapping with a previous run, recommend comparison tests
    if overlaps_previous_run:
        recommended_tests.append({
            'id': 'idt',
            'name': 'Inclination Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows inclination comparison'
        })
        recommended_tests.append({
            'id': 'adt',
            'name': 'Azimuth Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows azimuth comparison'
        })
        recommended_tests.append({
            'id': 'codt',
            'name': 'Co-ordinate Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows final coordinate comparison'
        })
        # All terms can be controlled with a full independent survey comparison
        uncontrolled_error_terms = []
    else:
        not_recommended_tests.append({
            'id': 'idt',
            'name': 'Inclination Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
        not_recommended_tests.append({
            'id': 'adt',
            'name': 'Azimuth Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
        not_recommended_tests.append({
            'id': 'codt',
            'name': 'Co-ordinate Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
    
    # Make sure we don't have any duplicates between recommended and not recommended
    recommended_ids = [test['id'] for test in recommended_tests]
    not_recommended_tests = [test for test in not_recommended_tests if test['id'] not in recommended_ids]
    
    # Prepare response
    response = {
        'recommended_tests': recommended_tests,
        'not_recommended_tests': not_recommended_tests,
        'uncontrolled_error_terms': uncontrolled_error_terms,
        'survey_station': {
            'tool_type': tool_type,
            'depth': current_station.get('depth', 0)
        },
        'test_context': {
            'stations_in_current_survey': len(current_survey),
            'overlaps_previous_run': overlaps_previous_run,
            'is_in_run_out_run_available': is_in_run_out_run_available,
            'is_bha_mounted': is_bha_mounted,
            'has_ccl': has_ccl
        }
    }
    
    return jsonify(response)

@recommendations_bp.route('/recommend-tests-batch', methods=['POST'])
def recommend_tests_batch():
    """Recommend tests for multiple survey stations in one request"""
    data = request.get_json()
    
    # Extract batch input parameters
    tool_type = data.get('tool_type', '')  # MWD, Gyro, Other
    survey_stations = data.get('survey_stations', [])
    full_survey = data.get('full_survey', [])  # All stations in the survey
    overlaps_previous_run = data.get('overlaps_previous_run', False)
    is_bha_mounted = data.get('is_bha_mounted', False)
    is_constant_toolface = data.get('is_constant_toolface', False)
    has_ccl = data.get('has_ccl', False)
    is_in_drillpipe = data.get('is_in_drillpipe', False)
    is_in_run_out_run_available = data.get('is_in_run_out_run_available', False)
    
    # Initialize result dictionary
    batch_results = {}
    
    # Calculate multistation recommendations once (since they apply to all stations)
    multistation_recommendations = []
    not_recommended_multistation = []
    
    # Evaluate multistation tests based on full survey data
    if len(full_survey) >= 10:
        if tool_type.lower() == 'mwd':
            multistation_recommendations.append({
                'id': 'msat',
                'name': 'Multi-Station Accelerometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze accelerometer errors'
            })
            multistation_recommendations.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze magnetometer errors'
            })
            
            # MSGT is not applicable for MWD
            not_recommended_multistation.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Not applicable for MWD tools that do not have gyroscopes'
            })
            
            # If really complex, recommend MSE
            if len(full_survey) >= 15:
                multistation_recommendations.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'priority': 'low',
                    'reason': 'Comprehensive error analysis possible with sufficient stations'
                })
            else:
                not_recommended_multistation.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
                })
                
        elif tool_type.lower() == 'gyro':
            multistation_recommendations.append({
                'id': 'msat',
                'name': 'Multi-Station Accelerometer Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze accelerometer errors'
            })
            multistation_recommendations.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'priority': 'medium',
                'reason': 'Sufficient stations available to analyze gyro errors'
            })
            
            # MSMT is not applicable for gyro
            not_recommended_multistation.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Not applicable for gyro tools that do not have magnetometers'
            })
            
            # MSE is usually not needed for gyro but can be used
            if len(full_survey) >= 15:
                multistation_recommendations.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'priority': 'low',
                    'reason': 'Comprehensive error analysis possible with sufficient stations'
                })
            else:
                not_recommended_multistation.append({
                    'id': 'mse',
                    'name': 'Multi-Station Estimation',
                    'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
                })
    else:
        # Not enough stations for multi-station tests
        not_recommended_multistation.append({
            'id': 'msat',
            'name': 'Multi-Station Accelerometer Test',
            'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
        })
        
        if tool_type.lower() == 'mwd':
            not_recommended_multistation.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
            })
            not_recommended_multistation.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Not applicable for MWD tools that do not have gyroscopes'
            })
        elif tool_type.lower() == 'gyro':
            not_recommended_multistation.append({
                'id': 'msgt',
                'name': 'Multi-Station Gyro Test',
                'reason': 'Insufficient stations available (requires at least 10 stations for reliable results)'
            })
            not_recommended_multistation.append({
                'id': 'msmt',
                'name': 'Multi-Station Magnetometer Test',
                'reason': 'Not applicable for gyro tools that do not have magnetometers'
            })
        
        not_recommended_multistation.append({
            'id': 'mse',
            'name': 'Multi-Station Estimation',
            'reason': 'Insufficient stations available (requires at least 15 stations for reliable results)'
        })
        
    # Calculate common recommendations for all stations
    common_not_recommended = []
    
    # For BHA-mounted tools, recommend rotation shot tests or not
    if is_bha_mounted and not is_constant_toolface:
        rsmt_recommendation = {
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'priority': 'medium',
            'reason': 'BHA-mounted tool with variable toolface allows misalignment control'
        }
    else:
        common_not_recommended.append({
            'id': 'rsmt',
            'name': 'Rotation-Shot Misalignment Test',
            'reason': 'Not applicable for tools that are not BHA-mounted or have constant toolface'
        })
    
    # For wireline surveys with CCL, recommend DDDT or not
    if has_ccl and is_in_drillpipe:
        dddt_recommendation = {
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'priority': 'medium',
            'reason': 'CCL and drillpipe depths available for comparison'
        }
    else:
        common_not_recommended.append({
            'id': 'dddt',
            'name': 'Dual Depth Difference Test',
            'reason': 'Not applicable without CCL in drillpipe (requires two independent depth measurements)'
        })
    
    # For surveys with in-run/out-run data
    if is_in_run_out_run_available:
        iomt_recommendation = {
            'id': 'iomt',
            'name': 'In-Run/Out-Run Misalignment Test',
            'priority': 'high',
            'reason': 'In-run/out-run data available for misalignment control'
        }
        cadt_recommendation = {
            'id': 'cadt',
            'name': 'Continuous Azimuth Drift Test',
            'priority': 'high',
            'reason': 'In-run/out-run data available for drift control'
        }
    else:
        common_not_recommended.append({
            'id': 'iomt',
            'name': 'In-Run/Out-Run Misalignment Test',
            'reason': 'Not applicable without in-run/out-run data'
        })
        common_not_recommended.append({
            'id': 'cadt',
            'name': 'Continuous Azimuth Drift Test',
            'reason': 'Not applicable without in-run/out-run data'
        })
    
    # For overlapping surveys
    if overlaps_previous_run:
        idt_recommendation = {
            'id': 'idt',
            'name': 'Inclination Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows inclination comparison'
        }
        adt_recommendation = {
            'id': 'adt',
            'name': 'Azimuth Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows azimuth comparison'
        }
        codt_recommendation = {
            'id': 'codt',
            'name': 'Co-ordinate Difference Test',
            'priority': 'high',
            'reason': 'Overlapping survey allows final coordinate comparison'
        }
    else:
        common_not_recommended.append({
            'id': 'idt',
            'name': 'Inclination Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
        common_not_recommended.append({
            'id': 'adt',
            'name': 'Azimuth Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
        common_not_recommended.append({
            'id': 'codt',
            'name': 'Co-ordinate Difference Test',
            'reason': 'Not applicable without overlapping survey data'
        })
    
    # Now process each station in the batch
    for station in survey_stations:
        depth = station.get('depth')
        if depth is None:
            continue  # Skip stations without depth information
            
        recommended_tests = []
        not_recommended_tests = []
        uncontrolled_error_terms = []
        
        # Add basic checks for this station based on tool type
        if tool_type.lower() == 'mwd':
            recommended_tests.append({
                'id': 'get',
                'name': 'Gravity Error Test',
                'priority': 'high',
                'reason': 'Basic verification of accelerometer integrity'
            })
            recommended_tests.append({
                'id': 'tfdt',
                'name': 'Total Field + Dip Test',
                'priority': 'high',
                'reason': 'Basic verification of magnetometer integrity'
            })
            
            # HERT is not applicable for MWD
            not_recommended_tests.append({
                'id': 'hert',
                'name': 'Horizontal Earth Rate Test',
                'reason': 'Not applicable for MWD tools that do not have gyroscopes'
            })
            
            uncontrolled_error_terms.extend(['sag', 'misalignments', 'declination', 'depth terms'])
            
        elif tool_type.lower() == 'gyro':
            recommended_tests.append({
                'id': 'get',
                'name': 'Gravity Error Test',
                'priority': 'high',
                'reason': 'Basic verification of accelerometer integrity'
            })
            recommended_tests.append({
                'id': 'hert',
                'name': 'Horizontal Earth Rate Test',
                'priority': 'high',
                'reason': 'Basic verification of gyroscope integrity'
            })
            
            # TFDT is not applicable for gyro
            not_recommended_tests.append({
                'id': 'tfdt',
                'name': 'Total Field + Dip Test',
                'reason': 'Not applicable for gyro tools that do not have magnetometers'
            })
            
            uncontrolled_error_terms.extend(['sag', 'misalignments', 'depth terms'])
        
        # Add station-specific recommendations based on common calculations
        if is_bha_mounted and not is_constant_toolface:
            recommended_tests.append(rsmt_recommendation)
            # Remove misalignments from uncontrolled since RSMT will control them
            if 'misalignments' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('misalignments')
                
        if has_ccl and is_in_drillpipe:
            recommended_tests.append(dddt_recommendation)
            # Remove depth terms from uncontrolled
            if 'depth terms' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('depth terms')
                
        if is_in_run_out_run_available:
            recommended_tests.append(iomt_recommendation)
            recommended_tests.append(cadt_recommendation)
            # Remove misalignments from uncontrolled since IOMT will control them
            if 'misalignments' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('misalignments')
                
        if overlaps_previous_run:
            recommended_tests.append(idt_recommendation)
            recommended_tests.append(adt_recommendation)
            recommended_tests.append(codt_recommendation)
            # All terms can be controlled with a full independent survey comparison
            uncontrolled_error_terms = []
        
        # Add multistation tests if applicable (these would be run once for the whole survey)
        # For the first station in the batch, include multistation recommendations
        if depth == survey_stations[0].get('depth'):
            recommended_tests.extend(multistation_recommendations)
            
            # If using multistation tests, remove misalignments from uncontrolled if applicable
            if multistation_recommendations and 'misalignments' in uncontrolled_error_terms:
                uncontrolled_error_terms.remove('misalignments')
        
        # Compile not_recommended_tests
        not_recommended_tests.extend(common_not_recommended)
        
        # For the first station in the batch, include not recommended multistation tests
        if depth == survey_stations[0].get('depth'):
            not_recommended_tests.extend(not_recommended_multistation)
        
        # Remove duplicates
        recommended_ids = [test['id'] for test in recommended_tests]
        not_recommended_tests = [test for test in not_recommended_tests if test['id'] not in recommended_ids]
        
        # Store results for this station
        batch_results[str(depth)] = {
            'recommended_tests': recommended_tests,
            'not_recommended_tests': not_recommended_tests,
            'uncontrolled_error_terms': uncontrolled_error_terms,
            'survey_station_info': {
                'depth': depth,
                'inclination': station.get('inclination'),
                'azimuth': station.get('azimuth')
            }
        }
    
    # Add overall survey context to the response
    response = {
        'batch_results': batch_results,
        'survey_context': {
            'tool_type': tool_type,
            'total_stations': len(full_survey),
            'batch_stations': len(survey_stations),
            'overlaps_previous_run': overlaps_previous_run,
            'is_in_run_out_run_available': is_in_run_out_run_available,
            'is_bha_mounted': is_bha_mounted,
            'has_ccl': has_ccl
        }
    }
    
    return jsonify(response)