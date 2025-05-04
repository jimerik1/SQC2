#!/usr/bin/env python3
"""
Test the sag correction API endpoint with a hardcoded payload and visualize the results.

This script:
1. Uses a hardcoded payload containing BHA and trajectory data
2. Calls the sag correction API endpoint
3. Plots the results showing:
   - Deflection (m)
   - Slope (deg) 
   - Bending moment (kN·m)
   - Shear force (kN)
   - Centralizer positions
   - D&I sensor position

Usage:
    python test_sag_api.py [api_url]

Default:
    api_url → http://localhost:5199/api/v1/corrections/sag
"""

import sys
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import requests


# Hardcoded payload data
PAYLOAD = {
  "trajectory": [
    {"md": 2340.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2370.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2400.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2430.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2460.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2490.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2520.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2550.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2580.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2610.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2640.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2670.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2700.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2730.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2760.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2790.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2820.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2850.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2880.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2910.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2940.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 2970.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3000.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3030.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3060.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3090.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3120.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3150.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3180.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3210.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3240.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3270.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3300.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3330.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3360.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3390.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3420.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3450.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3480.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3510.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3540.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3570.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3600.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3630.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3660.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3690.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3720.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3750.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3780.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3810.0, "inc": 41.8129, "azi": 114.5702},
    {"md": 3835.6594, "inc": 41.8129, "azi": 114.5702},
    {"md": 3840.0, "inc": 41.8, "azi": 115.2211},
    {"md": 3870.0, "inc": 41.8118, "azi": 119.722},
    {"md": 3900.0, "inc": 41.9987, "azi": 124.2056},
    {"md": 3930.0, "inc": 42.3585, "azi": 128.642},
    {"md": 3960.0, "inc": 42.8866, "azi": 133.0037},
    {"md": 3990.0, "inc": 43.5767, "azi": 137.2668},
    {"md": 4020.0, "inc": 44.4209, "azi": 141.4116},
    {"md": 4050.0, "inc": 45.4104, "azi": 145.4234},
    {"md": 4080.0, "inc": 46.5354, "azi": 149.2919},
    {"md": 4110.0, "inc": 47.7858, "azi": 153.0114},
    {"md": 4140.0, "inc": 49.1516, "azi": 156.5801},
    {"md": 4170.0, "inc": 50.6229, "azi": 159.9992},
    {"md": 4200.0, "inc": 52.1899, "azi": 163.2727},
    {"md": 4230.0, "inc": 53.8437, "azi": 166.4065},
    {"md": 4260.0, "inc": 55.5758, "azi": 169.4079},
    {"md": 4290.0, "inc": 57.3781, "azi": 172.285},
    {"md": 4320.0, "inc": 59.2434, "azi": 175.0467},
    {"md": 4350.0, "inc": 61.1649, "azi": 177.7018},
    {"md": 4380.0, "inc": 63.1366, "azi": 180.2594},
    {"md": 4410.0, "inc": 65.1526, "azi": 182.7283},
    {"md": 4440.0, "inc": 67.2079, "azi": 185.1174},
    {"md": 4470.0, "inc": 69.2977, "azi": 187.4349},
    {"md": 4500.0, "inc": 71.4177, "azi": 189.6889},
    {"md": 4530.0, "inc": 73.5638, "azi": 191.8872},
    {"md": 4560.0, "inc": 75.7322, "azi": 194.0372},
    {"md": 4590.0, "inc": 77.9196, "azi": 196.146},
    {"md": 4620.0, "inc": 80.1226, "azi": 198.2205},
    {"md": 4650.0, "inc": 82.3381, "azi": 200.2673},
    {"md": 4680.0, "inc": 84.5632, "azi": 202.2928},
    {"md": 4681.2034, "inc": 84.6526, "azi": 202.3737},
    {"md": 4710.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4740.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4770.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4800.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4830.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4860.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4890.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4920.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4950.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 4980.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5010.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5040.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5070.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5100.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5130.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5160.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5190.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5220.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5250.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5280.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5310.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5340.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5370.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5400.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5430.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5460.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5490.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5520.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5550.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5580.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5610.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5640.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5670.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5700.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5730.0, "inc": 84.6526, "azi": 202.3737},
    {"md": 5754.222, "inc": 84.6526, "azi": 202.3737},
    {"md": 5760.0, "inc": 85.2304, "azi": 202.9515},
    {"md": 5790.0, "inc": 88.2304, "azi": 205.9515},
    {"md": 5797.6959, "inc": 89.0, "azi": 206.7211},
    {"md": 5820.0, "inc": 88.9737, "azi": 204.4905},
    {"md": 5850.0, "inc": 88.9407, "azi": 201.4902},
    {"md": 5880.0, "inc": 88.9106, "azi": 198.4898},
    {"md": 5910.0, "inc": 88.8836, "azi": 195.4894},
    {"md": 5940.0, "inc": 88.8596, "azi": 192.4889},
    {"md": 5970.0, "inc": 88.8387, "azi": 189.4884},
    {"md": 6000.0, "inc": 88.821, "azi": 186.4878},
    {"md": 6030.0, "inc": 88.8065, "azi": 183.4872},
    {"md": 6060.0, "inc": 88.7953, "azi": 180.4866},
    {"md": 6090.0, "inc": 88.7874, "azi": 177.4859},
    {"md": 6120.0, "inc": 88.7828, "azi": 174.4852},
    {"md": 6150.0, "inc": 88.7816, "azi": 171.4846},
    {"md": 6180.0, "inc": 88.7837, "azi": 168.4839},
    {"md": 6210.0, "inc": 88.7892, "azi": 165.4832},
    {"md": 6240.0, "inc": 88.7979, "azi": 162.4826},
    {"md": 6270.0, "inc": 88.81, "azi": 159.4819},
    {"md": 6300.0, "inc": 88.8253, "azi": 156.4813},
    {"md": 6330.0, "inc": 88.8438, "azi": 153.4808},
    {"md": 6360.0, "inc": 88.8655, "azi": 150.4803},
    {"md": 6390.0, "inc": 88.8903, "azi": 147.4798},
    {"md": 6420.0, "inc": 88.9182, "azi": 144.4794},
    {"md": 6450.0, "inc": 88.949, "azi": 141.479},
    {"md": 6480.0, "inc": 88.9827, "azi": 138.4787},
    {"md": 6510.0, "inc": 89.0192, "azi": 135.4785},
    {"md": 6540.0, "inc": 89.0584, "azi": 132.4783},
    {"md": 6570.0, "inc": 89.1002, "azi": 129.4782},
    {"md": 6576.9589, "inc": 89.1102, "azi": 128.7823},
    {"md": 6600.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6630.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6660.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6690.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6720.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6750.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6780.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6810.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6840.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6870.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6900.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6930.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6960.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 6990.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7020.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7050.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7080.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7110.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7140.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7170.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7200.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7230.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7260.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7290.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7320.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7350.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7380.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7410.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7440.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7470.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7500.0, "inc": 89.1102, "azi": 128.7823},
    {"md": 7506.2251, "inc": 89.1102, "azi": 128.7823}
  ],
  "bha": {
    "structure": [
      {
        "description": "Bit",
        "od": 0.2159,
        "id": 0.0826,
        "max_od": 0.4064,
        "length": 0.41,
        "weight": 0.25,
        "material": "STEEL"
      },
      {
        "description": "Motor",
        "od": 0.2452,
        "id": 0.1994,
        "max_od": 0.4032,
        "length": 10.03,
        "weight": 2.48,
        "material": "STEEL"
      },
      {
        "description": "NM SS",
        "od": 0.2045,
        "id": 0.0762,
        "max_od": 0.308,
        "length": 2.23,
        "weight": 0.5299999999999998,
        "material": "NON_MAGNETIC"
      },
      {
        "description": "GWD",
        "od": 0.2136,
        "id": 0.1473,
        "max_od": 0.2136,
        "length": 4.6,
        "weight": 0.8600000000000003,
        "material": "STEEL"
      },
      {
        "description": "MWD",
        "od": 0.2134,
        "id": 0.1499,
        "max_od": 0.2134,
        "length": 8.37,
        "weight": 1.5599999999999996,
        "material": "STEEL"
      },
      {
        "description": "LWD",
        "od": 0.2139,
        "id": 0.0714,
        "max_od": 0.2324,
        "length": 5.87,
        "weight": 1.1600000000000001,
        "material": "STEEL"
      },
      {
        "description": "Non-mag Crossover",
        "od": 0.2096,
        "id": 0.0826,
        "max_od": 0.2096,
        "length": 0.78,
        "weight": 0.17999999999999972,
        "material": "STEEL"
      },
      {
        "description": "NM SS",
        "od": 0.2037,
        "id": 0.0762,
        "max_od": 0.4032,
        "length": 2.46,
        "weight": 0.5800000000000001,
        "material": "NON_MAGNETIC"
      },
      {
        "description": "Collar",
        "od": 0.2108,
        "id": 0.073,
        "max_od": 0.2108,
        "length": 9.48,
        "weight": 2.280000000000001,
        "material": "STEEL"
      },
      {
        "description": "Sub",
        "od": 0.207,
        "id": 0.0606,
        "max_od": 0.207,
        "length": 3.92,
        "weight": 0.75,
        "material": "STEEL"
      },
      {
        "description": "Sub",
        "od": 0.2,
        "id": 0.073,
        "max_od": 0.2,
        "length": 0.82,
        "weight": 0.16999999999999993,
        "material": "STEEL"
      },
      {
        "description": "Collar",
        "od": 0.2108,
        "id": 0.073,
        "max_od": 0.2108,
        "length": 18.96,
        "weight": 4.559999999999999,
        "material": "STEEL"
      },
      {
        "description": "Jar",
        "od": 0.2032,
        "id": 0.0762,
        "max_od": 0.205,
        "length": 10.21,
        "weight": 1.6799999999999997,
        "material": "STEEL"
      },
      {
        "description": "Collar",
        "od": 0.1595,
        "id": 0.0826,
        "max_od": 0.2009,
        "length": 9.18,
        "weight": 1.6600000000000001,
        "material": "STEEL"
      },
      {
        "description": "Collar",
        "od": 0.1595,
        "id": 0.073,
        "max_od": 0.2024,
        "length": 8.93,
        "weight": 1.620000000000001,
        "material": "STEEL"
      },
      {
        "description": "Sub",
        "od": 0.2048,
        "id": 0.0826,
        "max_od": 0.2048,
        "length": 1.02,
        "weight": 0.21999999999999886,
        "material": "STEEL"
      },
      {
        "description": "HWDP",
        "od": 0.127,
        "id": 0.073,
        "max_od": 0.1715,
        "length": 8.82,
        "weight": 0.8399999999999999,
        "material": "STEEL"
      },
      {
        "description": "Sub",
        "od": 0.1651,
        "id": 0.0826,
        "max_od": 0.1651,
        "length": 0.55,
        "weight": 0.07000000000000028,
        "material": "STEEL"
      },
      {
        "description": "HWDP",
        "od": 0.127,
        "id": 0.0762,
        "max_od": 0.1683,
        "length": 56.4,
        "weight": 4.23,
        "material": "STEEL"
      },
      {
        "description": "DP",
        "od": 0.127,
        "id": 0.1086,
        "max_od": 0.1651,
        "length": 9.45,
        "weight": 0.3200000000000003,
        "material": "STEEL"
      }
    ],
    "stabilizers": [
      {
        "blade_od": 0.4032,
        "distance_to_bit": 1.15,
        "length": 0.38
      },
      {
        "blade_od": 0.308,
        "distance_to_bit": 11.4,
        "length": 0.67
      },
      {
        "blade_od": 0.4032,
        "distance_to_bit": 33.5,
        "length": 0.84
      }
    ]
  },
  "sensor_position": 21.37,
  "mud_weight": 1.14,
  "dni_uphole_length": 25.0,
  "physical_constants": {
    "ro_steel": 7850.0,
    "e_steel": 205000000000.0,
    "e_nmag": 190000000000.0
  },
  "toolface": 0.0
}


def call_sag_correction_api(api_url: str):
    """
    Call the sag correction API endpoint with the hardcoded payload.
    
    Args:
        api_url: The URL of the API endpoint
        
    Returns:
        response_data: API response data
    """
    # Make API request
    try:
        response = requests.post(api_url, json=PAYLOAD)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling API: {e}")
        sys.exit(1)


def plot_sag_correction_results(response_data):
    """
    Plot sag correction results from API response.
    """
    # Extract grid data
    grid_data = response_data["grid_data"]
    sensor_position = response_data["sensor_position"]
    
    # Extract centralizer positions directly from hardcoded data
    centralizer_positions = [stab["distance_to_bit"] for stab in PAYLOAD["bha"]["stabilizers"]]
    
    # Convert to numpy arrays for plotting
    z = np.array([point["z_from_bit_m"] for point in grid_data])
    defl = np.array([point["deflection_m"] for point in grid_data])
    slope = np.array([point["slope_deg"] for point in grid_data])
    moment = np.array([point["moment_Nm"] for point in grid_data]) / 1e3  # Convert to kN·m
    shear = np.array([point["shear_N"] for point in grid_data]) / 1e3  # Convert to kN
    
    # Create plots
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(10, 9))
    
    def add_markers(ax):
        ax.axhline(0, ls=":", color="gray", linewidth=0.8)  # center line
        for x in centralizer_positions:
            ax.plot([x], [0], "kv", ms=7, zorder=5)  # centralizer
        ax.axvline(sensor_position, ls="--", color="red", linewidth=1.0)  # sensor
    
    # Plot deflection
    axes[0].plot(z, defl)
    add_markers(axes[0])
    axes[0].set_ylabel("Deflection (m)")
    axes[0].set_title("BHA Deflected Shape")
    
    # Plot slope
    axes[1].plot(z, slope)
    add_markers(axes[1])
    axes[1].set_ylabel("Slope (°)")
    
    # Plot moment
    axes[2].plot(z, moment)
    add_markers(axes[2])
    axes[2].set_ylabel("Moment (kN·m)")
    
    # Plot shear
    axes[3].plot(z, shear)
    add_markers(axes[3])
    axes[3].set_ylabel("Shear (kN)")
    axes[3].set_xlabel("Distance from bit (m)")
    
    plt.tight_layout()
    plt.show()


def main():
    # Parse command line arguments
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5199/api/v1/corrections/sag"
    
    print(f"Calling sag correction API at {api_url}...")
    response_data = call_sag_correction_api(api_url)
    
    # Plot results
    print("Plotting results...")
    plot_sag_correction_results(response_data)


if __name__ == "__main__":
    main()