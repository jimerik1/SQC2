# Directional Survey Quality Control API

A Flask-based RESTful API for validating, analyzing, and correcting directional survey data used in wellbore positioning. This system implements quality control methods described in the SPE paper "The Reliability Problem Related to Directional Survey Data" (IADC/SPE 103734) by Ekseth et al.

## Overview

This API provides endpoints to:
- Validate survey measurements against theoretical values
- Apply sophisticated QC tests to survey data
- Correct survey data using various algorithms
- Parse and use Instrument Performance Model (IPM) files

## Installation

### Prerequisites
- Python 3.9+
- Docker and Docker Compose (for containerized deployment)

### Local Development Setup

1. Clone the repository
```bash
git clone https://github.com/your-username/directional-survey-qc.git
cd directional-survey-qc
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Run the development server
```bash
flask run
# or
python wsgi.py
```

### Docker Deployment

1. Build and start the container
```bash
docker-compose up -d
```

2. The API will be available at `http://localhost:5199`

## API Endpoints

### Health Check
- **GET** `/healthz`
  - Returns health status of the API
  - Example response: `{"status": "healthy"}`

### Survey Routes (`/api/v1/survey/`)

#### Validate a Single Survey
- **POST** `/api/v1/survey/validate`
  - Validates a single survey measurement against quality criteria
  - Example payload:
  ```json
  {
    "depth": 2000.5,
    "inclination": 45.2,
    "azimuth": 102.7,
    "toolface": 186.3,
    "Gx": 0.707,
    "Gy": 0.0,
    "Gz": 0.707
  }
  ```
  - Example response:
  ```json
  {
    "is_valid": true,
    "errors": [],
    "warnings": [
      "Accelerometer magnitude 0.997g differs from expected 1g"
    ]
  }
  ```

#### Validate Multiple Surveys
- **POST** `/api/v1/survey/validate-batch`
  - Validates multiple survey measurements
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "depth": 2000.5,
        "inclination": 45.2,
        "azimuth": 102.7,
        "toolface": 186.3,
        "Gx": 0.707,
        "Gy": 0.0,
        "Gz": 0.707
      },
      {
        "depth": 2030.5,
        "inclination": 45.5,
        "azimuth": 103.2,
        "toolface": 187.1,
        "Gx": 0.708,
        "Gy": 0.0,
        "Gz": 0.706
      }
    ]
  }
  ```
  - Example response:
  ```json
  {
    "results": [
      {
        "is_valid": true,
        "errors": [],
        "warnings": [
          "Accelerometer magnitude 0.997g differs from expected 1g"
        ]
      },
      {
        "is_valid": true,
        "errors": [],
        "warnings": []
      }
    ]
  }
  ```

#### Analyze Surveys
- **POST** `/api/v1/survey/analyze`
  - Analyzes a set of survey measurements for consistency and trends
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "depth": 2000.5,
        "inclination": 45.2,
        "azimuth": 102.7,
        "toolface": 186.3
      },
      {
        "depth": 2030.5,
        "inclination": 45.5,
        "azimuth": 103.2,
        "toolface": 187.1
      },
      {
        "depth": 2060.5,
        "inclination": 45.8,
        "azimuth": 103.7,
        "toolface": 187.8
      }
    ]
  }
  ```
  - Example response:
  ```json
  {
    "statistics": {
      "count": 3,
      "depth": {
        "min": 2000.5,
        "max": 2060.5,
        "average": 2030.5
      },
      "inclination": {
        "min": 45.2,
        "max": 45.8,
        "average": 45.5
      },
      "azimuth": {
        "min": 102.7,
        "max": 103.7,
        "average": 103.2
      },
      "dogleg_severity": {
        "min": 0.83,
        "max": 0.89,
        "average": 0.86
      }
    },
    "consistency": {
      "depth_spacing": {
        "min": 30.0,
        "max": 30.0,
        "average": 30.0,
        "std_dev": 0.0
      }
    },
    "anomalies": []
  }
  ```

#### Correct Surveys
- **POST** `/api/v1/survey/correct`
  - Applies corrections to survey data based on error terms
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "depth": 2000.5,
        "inclination": 45.2,
        "azimuth": 102.7,
        "toolface": 186.3,
        "Gx": 0.707,
        "Gy": 0.0,
        "Gz": 0.707,
        "Bx": 22000,
        "By": 5000,
        "Bz": 40000,
        "expected_geomagnetic_field": {
          "total_field": 48000,
          "dip": 65,
          "declination": 4
        }
      }
    ]
  }
  ```
  - Example response:
  ```json
  [
    {
      "depth": 2000.5,
      "inclination": 45.23,
      "azimuth": 102.85,
      "toolface": 186.3,
      "Gx": 0.707,
      "Gy": 0.0,
      "Gz": 0.707,
      "Bx": 22000,
      "By": 5000,
      "Bz": 40000,
      "expected_geomagnetic_field": {
        "total_field": 48000,
        "dip": 65,
        "declination": 4
      }
    }
  ]
  ```

#### Export Survey Data
- **POST** `/api/v1/survey/export`
  - Corrects and exports survey data in specified format
  - Query parameters:
    - `format`: Output format (json, csv)
  - Example request: `POST /api/v1/survey/export?format=json`
  - Payload: Same as `/api/v1/survey/correct`
  - Example response: Same as `/api/v1/survey/correct` or CSV formatted data

### Single Station QC Tests (`/api/v1/qc/single-station/`)

#### Gravity Error Test (GET)
- **POST** `/api/v1/qc/single-station/get`
  - Performs Gravity Error Test on a survey station
  - Example payload:
  ```json
  {
    "survey": {
      "accelerometer_x": 0.707,
      "accelerometer_y": 0.0,
      "accelerometer_z": 0.707,
      "inclination": 45.0,
      "toolface": 180.0,
      "depth": 2000.0,
      "latitude": 60.0,
      "expected_gravity": 9.81
    },
    "ipm": "# IPM file contents here\nABXY-TI1S e s m/s2 0.0004 ...\nASXY-TI1S e s - 0.0005 ...\nABZ e s m/s2 0.0004 ...\nASZ e s - 0.0005 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "GET",
    "is_valid": true,
    "measurements": {
      "gravity": 0.9982
    },
    "theoretical_values": {
      "gravity": 1.0
    },
    "errors": {
      "gravity": -0.0018
    },
    "tolerances": {
      "gravity": 0.0015
    },
    "details": {
      "inclination": 45.0,
      "toolface": 180.0,
      "weighting_functions": {
        "wx": 0.0,
        "wy": -0.7071,
        "wz": 0.7071
      }
    }
  }
  ```

#### Total Field + Dip Test (TFDT)
- **POST** `/api/v1/qc/single-station/tfdt`
  - Performs Total Field + Dip Test on a survey station
  - Example payload:
  ```json
  {
    "survey": {
      "mag_x": 22000,
      "mag_y": 5000,
      "mag_z": 40000,
      "accelerometer_x": 0.707,
      "accelerometer_y": 0.0,
      "accelerometer_z": 0.707,
      "inclination": 45.0,
      "toolface": 180.0,
      "longitude": 5.0,
      "latitude": 60.0,
      "depth": 2000.0,
      "expected_geomagnetic_field": {
        "total_field": 48000,
        "dip": 65,
        "declination": 4
      }
    },
    "ipm": "# IPM file contents here\nMBX e s nT 100 ...\nMBY e s nT 100 ...\nMBZ e s nT 100 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "TFDT",
    "is_valid": true,
    "measurements": {
      "total_field": 47934.5,
      "dip": 64.8
    },
    "theoretical_values": {
      "total_field": 48000,
      "dip": 65.0
    },
    "errors": {
      "total_field": -65.5,
      "dip": -0.2
    },
    "tolerances": {
      "total_field": 400,
      "dip": 0.6
    },
    "details": {
      "is_valid_field": true,
      "is_valid_dip": true,
      "inclination": 45.0,
      "toolface": 180.0,
      "azimuth": 0.0,
      "latitude": 60.0
    }
  }
  ```

#### Horizontal Earth Rate Test (HERT)
- **POST** `/api/v1/qc/single-station/hert`
  - Performs Horizontal Earth Rate Test on a survey station
  - Example payload:
  ```json
  {
    "survey": {
      "gyro_x": 5.3,
      "gyro_y": 9.2,
      "inclination": 45.0,
      "azimuth": 60.0,
      "toolface": 180.0,
      "latitude": 60.0,
      "expected_horizontal_rate": 7.5
    },
    "ipm": "# IPM file contents here\nGBX e s deg/hr 0.1 ...\nGBY e s deg/hr 0.1 ...\nM e s deg/hr/g 0.1 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "HERT",
    "is_valid": true,
    "measurements": {
      "horizontal_rate": 10.6
    },
    "theoretical_values": {
      "horizontal_rate": 7.5
    },
    "errors": {
      "horizontal_rate": 3.1
    },
    "tolerances": {
      "horizontal_rate": 0.42
    },
    "details": {
      "inclination": 45.0,
      "azimuth": 60.0,
      "toolface": 180.0,
      "weighting_functions": [0.45, 0.78]
    }
  }
  ```

#### Rotation-Shot Misalignment Test (RSMT)
- **POST** `/api/v1/qc/single-station/rsmt`
  - Performs Rotation-Shot Misalignment Test on a set of survey measurements
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "inclination": 45.0,
        "toolface": 0.0
      },
      {
        "inclination": 45.1,
        "toolface": 90.0
      },
      {
        "inclination": 45.0,
        "toolface": 180.0
      },
      {
        "inclination": 44.9,
        "toolface": 270.0
      }
    ],
    "ipm": "# IPM file contents here\nMX e s deg 0.06 ...\nMY e s deg 0.06 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "RSMT",
    "is_valid": true,
    "measurements": {
      "misalignment_mx": 0.05,
      "misalignment_my": 0.1
    },
    "tolerances": {
      "misalignment_mx": 0.18,
      "misalignment_my": 0.18
    },
    "details": {
      "is_mx_valid": true,
      "is_my_valid": true,
      "parameter_correlation": 0.05,
      "residuals": [0.02, -0.01, 0.01],
      "residual_gate_deg": 0.1,
      "inclination_deg": 45.0,
      "quadrant_distribution": [1, 1, 1, 1]
    }
  }
  ```

### Measurement QC Tests

#### Dual Depth Difference Test (DDDT)
- **POST** `/api/v1/qc/measurement/dddt`
  - Performs Dual Depth Difference Test on pipe and wireline depth measurements
  - Example payload:
  ```json
  {
    "pipe_depth": 2000.5,
    "wireline_depth": 2000.2,
    "survey": {
      "inclination": 45.0,
      "azimuth": 60.0,
      "true_vertical_depth": 1414.2
    },
    "ipm": "# IPM file contents here\nDREF-PIPE e s m 0.3 ...\nDREF-WIRE e s m 0.3 ...\nDSF-PIPE e s - 0.0002 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "DDDT",
    "is_valid": true,
    "measurements": {
      "pipe_depth": 2000.5,
      "wireline_depth": 2000.2
    },
    "errors": {
      "depth_difference": 0.3
    },
    "tolerances": {
      "depth_difference": 3.7
    },
    "details": {
      "true_vertical_depth": 1414.2
    }
  }
  ```

### Multi-Station QC Tests (`/api/v1/qc/multi-station/`)

#### Multi-Station Accelerometer Test (MSAT)
- **POST** `/api/v1/qc/multi-station/msat`
  - Performs Multi-Station Accelerometer Test on a set of survey measurements
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "accelerometer_x": 0.0,
        "accelerometer_y": 0.0,
        "accelerometer_z": 1.0,
        "inclination": 0.0,
        "toolface": 0.0,
        "expected_gravity": 1.0
      },
      {
        "accelerometer_x": 0.7071,
        "accelerometer_y": 0.0,
        "accelerometer_z": 0.7071,
        "inclination": 45.0,
        "toolface": 0.0,
        "expected_gravity": 1.0
      },
      {
        "accelerometer_x": 0.0,
        "accelerometer_y": 0.7071,
        "accelerometer_z": 0.7071,
        "inclination": 45.0,
        "toolface": 90.0,
        "expected_gravity": 1.0
      }
      // At least 10 surveys with varying inclinations and toolfaces
    ],
    "ipm": "# IPM file contents here\nABXY-TI1S e s m/s2 0.0004 ...\nASXY-TI1S e s - 0.0005 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "MSAT",
    "is_valid": true,
    "measurements": {
      "ABX*": 0.0002,
      "ABY*": 0.0003,
      "ABZ*": 0.0001,
      "ASX": 0.00003,
      "ASY": 0.00002
    },
    "tolerances": {
      "ABX*": 0.0012,
      "ABY*": 0.0012,
      "ABZ*": 0.0012,
      "ASX": 0.0015,
      "ASY": 0.0015
    },
    "details": {
      "residuals": [0.0003, -0.0002, 0.0001, ...],
      "residual_tolerances": [0.0015, 0.0015, 0.0015, ...],
      "correlation_matrix": [[1.0, 0.05, -0.1, 0.03, 0.09], ...],
      "max_nondiagonal_correlation": 0.29,
      "model_type": "full",
      "inclination_variation_deg": 45.0,
      "quadrant_distribution": [3, 3, 2, 2]
    }
  }
  ```

#### Multi-Station Gyro Test (MSGT)
- **POST** `/api/v1/qc/multi-station/msgt`
  - Performs Multi-Station Gyro Test on a set of survey measurements
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "gyro_x": 0.0,
        "gyro_y": 7.5,
        "inclination": 0.0,
        "azimuth": 90.0,
        "toolface": 0.0,
        "latitude": 60.0
      },
      {
        "gyro_x": 5.3,
        "gyro_y": 5.3,
        "inclination": 45.0,
        "azimuth": 45.0,
        "toolface": 0.0,
        "latitude": 60.0
      }
      // At least 10 surveys with varying inclinations and azimuths
    ],
    "ipm": "# IPM file contents here\nGBX e s deg/hr 0.1 ...\nGBY e s deg/hr 0.1 ...\nM e s deg/hr/g 0.1 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "MSGT",
    "is_valid": true,
    "measurements": {
      "GBX*": 0.05,
      "GBY*": 0.03,
      "M": 0.08,
      "Q": 0.02
    },
    "tolerances": {
      "GBX*": 0.3,
      "GBY*": 0.3,
      "M": 0.3,
      "Q": 0.3
    },
    "details": {
      "residuals": [0.1, -0.08, 0.05, ...],
      "residual_tolerances": [0.42, 0.38, 0.45, ...],
      "correlation_matrix": [[1.0, 0.32, -0.07], ...],
      "max_nondiagonal_correlation": 0.32,
      "inclination_variation_deg": 45.0,
      "quadrant_distribution": [3, 3, 2, 2],
      "east_west_ratio": 0.3
    }
  }
  ```

#### Multi-Station Magnetometer Test (MSMT)
- **POST** `/api/v1/qc/multi-station/msmt`
  - Performs Multi-Station Magnetometer Test on a set of survey measurements
  - Example payload:
  ```json
  {
    "surveys": [
      {
        "mag_x": 0.0,
        "mag_y": 17000.0,
        "mag_z": 45000.0,
        "accelerometer_x": 0.0,
        "accelerometer_y": 0.0,
        "accelerometer_z": 1.0,
        "inclination": 0.0,
        "azimuth": 90.0,
        "toolface": 0.0,
        "expected_geomagnetic_field": {
          "total_field": 48000,
          "dip": 65,
          "declination": 4
        }
      },
      // At least 10 surveys with varying inclinations and azimuths
    ],
    "ipm": "# IPM file contents here\nMBX e s nT 100 ...\nMBY e s nT 100 ...\nMBZ e s nT 100 ..."
  }
  ```
  - Example response:
  ```json
  {
    "test_name": "MSMT",
    "is_valid": true,
    "measurements": {
      "MBX": 50,
      "MBY": 75,
      "MBZ": 25,
      "MSX": 0.00002,
      "MSY": 0.00001,
      "MSZ": 0.00003
    },
    "tolerances": {
      "MBX": 300,
      "MBY": 300,
      "MBZ": 300,
      "MSX": 0.0006,
      "MSY": 0.0006,
      "MSZ": 0.0006
    },
    "details": {
      "field_residuals": [20, -15, 25, ...],
      "dip_residuals": [0.1, -0.15, 0.05, ...],
      "field_tolerances": [400, 400, 400, ...],
      "dip_tolerances": [0.6, 0.6, 0.6, ...],
      "correlation_matrix": [[1.0, 0.15, 0.08, ...], ...],
      "max_nondiagonal_correlation": 0.28
    }
  }
  ```

#### Multi-Station Estimation (MSE)
- **POST** `/api/v1/qc/multi-station/mse`
  - Performs Multi-Station Estimation on a set of survey measurements
  - Example payload: Similar to MSMT with at least 10 surveys
  - Example response:
  ```json
  {
    "is_valid": true,
    "error_parameters": {
      "MBX": {
        "value": 48.5,
        "std_dev": 18.2,
        "t_statistic": 2.66,
        "significant": true,
        "within_tolerance": true
      },
      "MBY": {
        "value": 72.3,
        "std_dev": 19.5,
        "t_statistic": 3.71,
        "significant": true,
        "within_tolerance": true
      },
      "MBZ": {
        "value": 28.7,
        "std_dev": 22.1,
        "t_statistic": 1.3,
        "significant": false,
        "within_tolerance": true
      },
      // Other parameters...
    },
    "corrected_surveys": [
      {
        "inclination": 0.05,
        "azimuth": 89.8,
        "toolface": 0.1,
        // Original survey data with corrections
      },
      // Corrected surveys
    ],
    "correlations": [[1.0, 0.12, 0.05, ...], ...],
    "statistics": {
      "max_correlation": 0.32,
      "converged": true,
      "iterations": 5,
      "final_residual_norm": 0.85
    },
    "details": {
      "geometry_quality": "good",
      "inclination_variation": 45.2,
      "azimuth_variation": 178.5,
      "quadrant_distribution": [3, 3, 2, 2]
    }
  }
  ```

### Toolcode Routes (`/api/v1/toolcode/`)

#### Parse IPM File
- **POST** `/api/v1/toolcode/parse-ipm`
  - Parses and returns the contents of an IPM file
  - Example payload:
  ```json
  {
    "ipm_content": "# IPM file contents here\nABXY-TI1S e s m/s2 0.0004 ...\nASXY-TI1S e s - 0.0005 ..."
  }
  ```
  - Example response:
  ```json
  {
    "short_name": "ISCWSA-MWD-Rev4",
    "description": "ISCWSA MWD Error Model Revision 4",
    "error_terms": [
      {
        "name": "ABXY-TI1S",
        "vector": "e",
        "tie_on": "s",
        "unit_raw": "m/s2",
        "value_raw": 0.0004,
        "value": 0.0004,
        "unit": "m/s2",
        "formula": "..."
      },
      // Other error terms
    ]
  }
  ```

#### Get Error Term
- **POST** `/api/v1/toolcode/error-term`
  - Gets a specific error term from an IPM file
  - Example payload:
  ```json
  {
    "ipm_content": "# IPM file contents here\nABXY-TI1S e s m/s2 0.0004 ...\nASXY-TI1S e s - 0.0005 ...",
    "name": "ABXY-TI1S",
    "vector": "e",
    "tie_on": "s"
  }
  ```
  - Example response:
  ```json
  {
    "name": "ABXY-TI1S",
    "vector": "e",
    "tie_on": "s",
    "unit_raw": "m/s2",
    "value_raw": 0.0004,
    "value": 0.0004,
    "unit": "m/s2",
    "formula": "..."
  }
  ```

#### Get Supported Tests
- **GET** `/api/v1/toolcode/supported-tests`
  - Returns information about supported QC tests
  - Example response:
  ```json
  [
    {
      "id": "get",
      "name": "Gravity Error Test",
      "description": "Tests accelerometer measurements against theoretical gravity",
      "endpoint": "/api/v1/qc/single-station/get",
      "method": "POST"
    },
    {
      "id": "tfdt",
      "name": "Total Field + Dip Test",
      "description": "Tests magnetometer measurements against theoretical magnetic field",
      "endpoint": "/api/v1/qc/single-station/tfdt",
      "method": "POST"
    },
    // Other supported tests
  ]
  ```

## Background on Survey QC Tests

This API implements several QC tests for directional surveys as described in the SPE paper "The Reliability Problem Related to Directional Survey Data" (IADC/SPE 103734) by Ekseth et al. The tests include:

1. **GET (Gravity Error Test)** - Tests accelerometer measurements against theoretical gravity
2. **TFDT (Total Field + Dip Test)** - Tests magnetometer measurements against theoretical magnetic field
3. **HERT (Horizontal Earth Rate Test)** - Tests gyroscope measurements against theoretical Earth rotation rate
4. **RSMT (Rotation-Shot Misalignment Test)** - Tests for misalignment using measurements at different toolfaces
5. **DDDT (Dual Depth Difference Test)** - Tests depth measurements from two independent systems
6. **MSAT (Multi-Station Accelerometer Test)** - Tests accelerometer errors using multiple survey stations
7. **MSGT (Multi-Station Gyro Test)** - Tests gyroscope errors using multiple survey stations
8. **MSMT (Multi-Station Magnetometer Test)** - Tests magnetometer errors using multiple survey stations
9. **MSE (Multi-Station Estimation)** - Comprehensive estimation of all systematic errors

## Error Models and IPM Files

The system uses ISCWSA (Industry Steering Committee on Wellbore Survey Accuracy) error models, defined in IPM (Instrument Performance Model) files. These files contain error terms that define the expected performance of surveying instruments.

The format of an IPM file entry is:
```
NAME VECTOR TIE_ON UNIT VALUE FORMULA
```

For example:
```
ABXY-TI1S e s m/s2 0.0004 Accelerometer bias term
```


