# Total Field + Dip Test (TFDT) API Endpoint

## Overview

The Total Field + Dip Test (TFDT) endpoint provides quality control for directional survey measurements by validating magnetometer and accelerometer readings against the expected geomagnetic field. Based on the methodology described in Ekseth et al. (2006), this test evaluates whether the measured magnetic field total magnitude and dip angle fall within acceptable tolerances.

## What It Does

The TFDT endpoint:

- Calculates the magnetic field magnitude from three-axis magnetometer readings
- Calculates the magnetic dip angle using magnetometer and accelerometer readings
- Automatically computes inclination, toolface, and azimuth from sensor readings
- Compares the calculated values to the expected geomagnetic field parameters
- Determines if the differences fall within acceptable tolerances (based on IPM error terms)
- Provides comprehensive quality warnings based on geometric limitations of the test

## Endpoint Information

- **URL**: `/api/v1/qc/single-station/tfdt`
- **Method**: POST
- **Content-Type**: application/json

## Request Format

```json
{
  "survey": {
    "mag_x": float,            // nT
    "mag_y": float,            // nT
    "mag_z": float,            // nT
    "accelerometer_x": float,  // g units
    "accelerometer_y": float,  // g units
    "accelerometer_z": float,  // g units
    "latitude": float,         // degrees (optional, used for warnings only)
    "expected_geomagnetic_field": {
      "total_field": float,    // nT
      "dip": float,            // degrees
      "declination": float     // degrees
    }
  },
  "ipm": string                // IPM file content
}
```

### Required Fields

- **mag_x, mag_y, mag_z**: The three-axis magnetometer readings in nanoTesla (nT)
- **accelerometer_x, accelerometer_y, accelerometer_z**: The three-axis accelerometer readings in g units
- **expected_geomagnetic_field**: Object containing reference geomagnetic field parameters:
  - **total_field**: Expected total magnetic field strength in nT
  - **dip**: Expected magnetic dip angle in degrees
  - **declination**: Expected magnetic declination in degrees

### Optional Fields

- **latitude**: Geomagnetic latitude for high-latitude warnings (degrees)

## Response Format

```json
{
  "test_name": "TFDT",
  "is_valid": true|false,
  "measurements": {
    "total_field": float,
    "dip": float
  },
  "theoretical_values": {
    "total_field": float,
    "dip": float
  },
  "errors": {
    "total_field": float,
    "dip": float
  },
  "tolerances": {
    "total_field": float,
    "dip": float
  },
  "details": {
    "is_valid_field": true|false,
    "is_valid_dip": true|false,
    "inclination": float,
    "toolface": float,
    "azimuth": float,
    "latitude": float,
    "weighting_functions": {
      "wbx_b": float,
      "wby_b": float,
      "wbz_b": float,
      "wbx_d": float,
      "wby_d": float,
      "wbz_d": float
    },
    "warnings": [
      {
        "code": string,
        "message": string
      },
      // possible warnings...
    ],
    "debug_ipm_terms": {
      // IPM term details, used error values, weighted contributions...
    }
  }
}
```

## Warning Types

The endpoint may return several warnings based on test limitations:

- **near_vertical**: When inclination is below 10° (test has reduced reliability)
- **near_horizontal**: When inclination is above 80° (test has reduced reliability)
- **cardinal_azimuth**: When azimuth is near cardinal directions (N/S or E/W)
- **high_mag_lat**: When geomagnetic latitude exceeds 60° (test has reduced reliability)

## Example Payloads

### Basic Request

```json
{
  "survey": {
    "mag_x": -37236.83276,
    "mag_y": 17259.14203,
    "mag_z": 32991.15012,
    "accelerometer_x": -0.277219206,
    "accelerometer_y": 0.606332248,
    "accelerometer_z": 0.745325913,
    "expected_geomagnetic_field": {
      "total_field": 51541.551,
      "dip": 73.484,
      "declination": 1.429
    }
  },
  "ipm": "#ShortName:MWD rev 3"
}
```

### Request with Latitude for Enhanced Warnings

```json
{
  "survey": {
    "mag_x": -37236.83276,
    "mag_y": 17259.14203,
    "mag_z": 32991.15012,
    "accelerometer_x": -0.277219206,
    "accelerometer_y": 0.606332248,
    "accelerometer_z": 0.745325913,
    "latitude": 60.5,
    "expected_geomagnetic_field": {
      "total_field": 51541.551,
      "dip": 73.484,
      "declination": 1.429
    }
  },
  "ipm": "#ShortName:MWD rev 3"
}
```

## Scientific Background

The Total Field + Dip Test is based on the methodologies described in Ekseth et al. (2006), "The Reliability Problem Related to Directional Survey Data" (IADC/SPE 103734). The test evaluates the magnetometer package by comparing the measured total field and dip angle to expected values.

The test's discriminatory power varies based on tool orientation and location:

- Reduced reliability near vertical (< 10°) or horizontal (> 80°) wells
- Reduced reliability when wellbore runs near cardinal directions (N/S or E/W)
- Reduced reliability at high geomagnetic latitudes (> 60°)

## Notes

- The endpoint automatically calculates inclination, toolface, and azimuth from sensor readings
- Declination errors cannot be detected by this test alone
- IPM file content is used to determine acceptable tolerances based on tool specifications
- The test checks both total field and dip angle; both must pass for the survey to be valid
- For highest reliability, multiple quality control tests should be used in combination
- The test is particularly useful for identifying magnetometer calibration issues and the effects of magnetic interference