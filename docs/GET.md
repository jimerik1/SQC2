# Gravity Error Test (GET) API Endpoint

## Overview

The Gravity Error Test (GET) endpoint provides quality control for directional survey measurements by validating accelerometer readings against the expected gravitational field. Based on the methodology described in Ekseth et al. (2006), this test evaluates whether the measured gravity magnitude falls within acceptable tolerances.

## What It Does

The GET endpoint:

- Calculates the gravitational field magnitude from three-axis accelerometer readings
- Compares the calculated gravity to the expected/theoretical gravity value
- Determines if the difference falls within acceptable tolerance (based on IPM error terms)
- Calculates inclination and toolface angles from accelerometer readings
- Provides comprehensive quality warnings based on geometric limitations of the test
- Validates provided inclination/toolface against calculated values (if provided)

## Endpoint Information

- **URL**: `/api/v1/qc/single-station/get`
- **Method**: POST
- **Content-Type**: application/json

## Request Format

```json
{
  "survey": {
    "accelerometer_x": float,  // g units
    "accelerometer_y": float,  // g units
    "accelerometer_z": float,  // g units
    "inclination": float,      // degrees (optional)
    "toolface": float,         // degrees (optional)
    "azimuth": float,          // degrees (optional)
    "depth": float,            // meters
    "expected_gravity": float  // g units (from EGM2008 API)
  },
  "ipm": string                // IPM file content
}
```

### Required Fields

- **accelerometer_x, accelerometer_y, accelerometer_z**: The three-axis accelerometer readings in g units
- **depth**: Measured depth in meters
- **expected_gravity**: Theoretical gravity at the given location (typically from Earth Gravity Model)

### Optional Fields

- **inclination**: Provided inclination angle for validation (degrees)
- **toolface**: Provided toolface angle for validation (degrees)
- **azimuth**: Provided azimuth angle for enhanced warnings (degrees)

## Response Format

```json
{
  "test": "GET",
  "is_valid": true|false,
  "measurements": {
    "gravity": float
  },
  "theoretical": {
    "gravity": float
  },
  "errors": {
    "gravity": float
  },
  "tolerances": {
    "gravity": float
  },
  "details": {
    "calculated_inclination": float,
    "calculated_toolface": float|null,
    "provided_inclination": float,  // if provided
    "provided_toolface": float,     // if provided
    "weighting_functions": {
      "wx": float,
      "wy": float,
      "wz": float
    },
    "warnings": [
      {
        "code": string,
        "message": string
      },
      // possible warnings...
    ],
    "debug_ipm_terms": {
      // IPM term details...
    }
  }
}
```

## Warning Types

The endpoint may return several warnings based on test limitations:

- **weak_geometry**: When inclination is outside optimal range (10° to 80°)
- **suboptimal_toolface**: When toolface is not near optimal values (45°, 135°, 225°, 315°)
- **cardinal_direction**: When azimuth is near cardinal directions (N/S or E/W)
- **suboptimal_geometry**: Combined warning for poor inclination and toolface
- **inclination_discrepancy**: When provided and calculated inclination differ significantly
- **toolface_discrepancy**: When provided and calculated toolface differ significantly
- **undefined_toolface**: When inclination is too low to reliably calculate toolface

## Example Payloads

### Basic Request

```json
{
  "survey": {
    "accelerometer_x": -4.977847106,
    "accelerometer_y": 2.381802169,
    "accelerometer_z": 8.110743284,
    "depth": -1080.0,
    "expected_gravity": 9.76
  },
  "ipm": "#ShortName:MWD rev 3"
}
```

### Request with Validation

```json
{
  "survey": {
    "accelerometer_x": -4.977847106,
    "accelerometer_y": 2.381802169,
    "accelerometer_z": 8.110743284,
    "inclination": 34.2303,
    "toolface": 45.178,
    "depth": -1080.0,
    "expected_gravity": 9.76
  },
  "ipm": "#ShortName:MWD rev 3"
}
```

### Request with Azimuth for Enhanced Warnings

```json
{
  "survey": {
    "accelerometer_x": -4.977847106,
    "accelerometer_y": 2.381802169,
    "accelerometer_z": 8.110743284,
    "inclination": 34.2303,
    "toolface": 45.178,
    "azimuth": 90.5,
    "depth": -1080.0,
    "expected_gravity": 9.76
  },
  "ipm": "#ShortName:MWD rev 3"
}
```

## Scientific Background

The Gravity Error Test is based on the methodologies described in Ekseth et al. (2006), "The Reliability Problem Related to Directional Survey Data" (IADC/SPE 103734). The test evaluates the accelerometer package by comparing measured gravity to the expected value.

The test's discriminatory power varies based on tool orientation:

- Optimal at 45° inclination with toolface at 45°, 135°, 225°, or 315°
- Reduced reliability near vertical or horizontal
- Reduced reliability at certain toolface angles
- Reduced reliability in wells running north/south or east/west

## Notes

- The test calculates inclination and toolface angles directly from accelerometer readings
- Toolface calculation is limited to inclinations ≥ 10° for reliability
- IPM file content is used to determine acceptable tolerances based on tool specifications
- For highest reliability, multiple quality control tests should be used in combination