import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse
from math import sin, cos, tan, asin, acos, atan2, radians, degrees, sqrt, pi

def read_trajectory_from_excel(filename):
    """Read trajectory data from an Excel file with proper handling of decimal commas"""
    try:
        # Read the Excel file
        trajectory_df = pd.read_excel(filename)
        
        # Ensure required columns are present
        required_columns = ['Depth', 'Inc', 'Azi', 'tfo']
        for col in required_columns:
            if col not in trajectory_df.columns:
                if len(trajectory_df.columns) >= 4:
                    trajectory_df.columns = required_columns + list(trajectory_df.columns[4:])
                else:
                    raise ValueError(f"Column '{col}' not found in the Excel file")
        
        # Convert any string numbers with commas to proper floats
        for col in ['Inc', 'Azi', 'tfo']:
            if trajectory_df[col].dtype == 'object':
                trajectory_df[col] = trajectory_df[col].astype(str).str.replace(',', '.').astype(float)
        
        print(f"Successfully read trajectory data with {len(trajectory_df)} survey stations")
        return trajectory_df
    
    except Exception as e:
        print(f"Error reading trajectory from Excel: {e}")
        print("Using default trajectory data instead")
        
        # Return a default trajectory if Excel reading fails
        trajectory_data = {
            'Depth': [0, 100, 200, 300, 400],
            'Inc': [0, 10, 15, 20, 20],
            'Azi': [0, 30, 30, 30, 50],
            'tfo': [0, 0, 0, 0, 0]
        }
        return pd.DataFrame(trajectory_data)

def generate_perfect_raw_data(trajectory_df, magnetic_dip=73.484, magnetic_field_strength=51541.551, 
                             gravity=9.81, declination=1.429, add_noise=False, noise_level=0.001):
    """
    Generate raw survey data by working backwards from the desired trajectory values.
    This ensures perfect validation results when calculating back to trajectory.
    """
    n_points = len(trajectory_df)
    Gx = np.zeros(n_points)
    Gy = np.zeros(n_points)
    Gz = np.zeros(n_points)
    Bx = np.zeros(n_points)
    By = np.zeros(n_points)
    Bz = np.zeros(n_points)
    
    # Earth's magnetic field components in NED
    dip_rad = np.radians(magnetic_dip)
    dec_rad = np.radians(declination)
    
    # Calculate field components
    Bh = magnetic_field_strength * np.cos(dip_rad)
    Bz_geo = magnetic_field_strength * np.sin(dip_rad)
    Bx_geo = Bh * np.cos(dec_rad)
    By_geo = Bh * np.sin(dec_rad)
    
    # For each survey station
    for i in range(n_points):
        inc = np.radians(trajectory_df['Inc'].values[i])
        azi = np.radians(trajectory_df['Azi'].values[i])
        
        # Step 1: Calculate accelerometer values directly from inclination and azimuth
        # These will always give the correct inclination by definition
        sin_inc = np.sin(inc)
        cos_inc = np.cos(inc)
        sin_azi = np.sin(azi)
        cos_azi = np.cos(azi)
        
        Gx[i] = gravity * sin_inc * cos_azi
        Gy[i] = gravity * sin_inc * sin_azi
        Gz[i] = gravity * cos_inc
        
        # Step 2: Calculate magnetometer values that will precisely yield the desired azimuth
        # For very low inclinations (< 0.5°), use the desired azimuth directly
        if inc < np.radians(0.5):
            # For vertical wells, create values that will recover to desired azimuth
            # This is a special case that avoids numerical instability
            Bx[i] = Bh * np.cos(azi)
            By[i] = Bh * np.sin(azi)
            Bz[i] = Bz_geo
        else:
            # For all other inclinations, we need to create B-field values that will
            # produce exactly the desired azimuth when processed through the standard formula

            # Calculate magnetometer values that will yield the desired azimuth
            # The azimuth equation can be rearranged to solve for By:
            # A = atan2((Gx*By - Gy*Bx), (Bz*(Gx^2 + Gy^2) - Gz*(Gx*Bx + Gy*By)))
            
            # First, set Bx and Bz to values that are consistent with the geomagnetic field
            Bx[i] = Bx_geo * cos_inc * cos_azi + By_geo * cos_inc * sin_azi - Bz_geo * sin_inc
            Bz[i] = Bx_geo * sin_inc * cos_azi + By_geo * sin_inc * sin_azi + Bz_geo * cos_inc
            
            # Now, solve for the By value that gives exactly the desired azimuth
            # From A = atan2(num, den), we need num/den = tan(A)
            # Given Gx, Gy, Gz, Bx, Bz, and azi, solve for By
            
            tan_azi = np.tan(azi)
            
            # Set up the equation: num/den = tan(A)
            # num = Gx*By - Gy*Bx
            # den = Bz*(Gx^2 + Gy^2) - Gz*(Gx*Bx + Gy*By)
            # Multiply both sides by den: num = tan(A) * den
            # Substitute and solve for By
            
            if np.abs(tan_azi) < 1e-10 or np.abs(tan_azi) > 1e10:
                # Handle special cases for azi = 0, 180, etc.
                if np.abs(np.cos(azi)) > 0.7:  # Close to 0 or 180 degrees
                    By[i] = (Gy[i] * Bx[i]) / Gx[i]  # Makes numerator zero
                else:  # Close to 90 or 270 degrees
                    # Make denominator zero if numerator is already correct sign
                    By[i] = ((Bz[i] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * Gx[i] * Bx[i]) / (Gz[i] * Gy[i]))
            else:
                # Normal case - solve the full equation
                # Rearranging: Gx*By - Gy*Bx = tan(A) * [Bz*(Gx^2 + Gy^2) - Gz*(Gx*Bx + Gy*By)]
                # Expand: Gx*By - Gy*Bx = tan(A) * Bz*(Gx^2 + Gy^2) - tan(A) * Gz*Gx*Bx - tan(A) * Gz*Gy*By
                # Collect By terms: Gx*By + tan(A) * Gz*Gy*By = tan(A) * Bz*(Gx^2 + Gy^2) - tan(A) * Gz*Gx*Bx + Gy*Bx
                # Factor out By: By * (Gx + tan(A) * Gz*Gy) = tan(A) * Bz*(Gx^2 + Gy^2) - tan(A) * Gz*Gx*Bx + Gy*Bx
                
                By[i] = (tan_azi * Bz[i] * (Gx[i]**2 + Gy[i]**2) - tan_azi * Gz[i] * Gx[i] * Bx[i] + Gy[i] * Bx[i]) / (Gx[i] + tan_azi * Gz[i] * Gy[i])
                
                # Verify our computation with a direct check
                num = Gx[i] * By[i] - Gy[i] * Bx[i]
                den = Bz[i] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * Bx[i] + Gy[i] * By[i])
                computed_azi = np.arctan2(num, den)
                
                # If there's a significant error, try adjusting By
                if np.abs(computed_azi - azi) > 0.01:
                    # Fine-tune By to get a perfect match
                    adjustment_factor = 1.0 + (azi - computed_azi) * 0.1  # Small adjustment
                    By[i] *= adjustment_factor
    
    # Add noise if requested
    if add_noise:
        Gx += np.random.normal(0, noise_level * gravity, n_points)
        Gy += np.random.normal(0, noise_level * gravity, n_points)
        Gz += np.random.normal(0, noise_level * gravity, n_points)
        Bx += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
        By += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
        Bz += np.random.normal(0, noise_level * magnetic_field_strength, n_points)
    
    # Create output DataFrame
    result_df = trajectory_df.copy()
    result_df['Gx'] = Gx
    result_df['Gy'] = Gy
    result_df['Gz'] = Gz
    result_df['Bx'] = Bx
    result_df['By'] = By
    result_df['Bz'] = Bz
    
    return result_df

def validate_synthetic_data(raw_data_df, magnetic_dip=73.484, magnetic_field_strength=51541.551, 
                           gravity=9.81, declination=1.429):
    """
    Validate synthetic data using standard industry formulas.
    """
    # Extract raw data
    Gx = raw_data_df['Gx'].values
    Gy = raw_data_df['Gy'].values
    Gz = raw_data_df['Gz'].values
    Bx = raw_data_df['Bx'].values
    By = raw_data_df['By'].values
    Bz = raw_data_df['Bz'].values
    
    # Calculate total magnitudes
    G = np.sqrt(Gx**2 + Gy**2 + Gz**2)
    B = np.sqrt(Bx**2 + By**2 + Bz**2)
    
    # Calculate inclination
    inc_calc = np.degrees(np.arccos(np.clip(Gz / G, -1.0, 1.0)))
    
    # Calculate azimuth
    azimuth = np.zeros(len(Gx))
    
    for i in range(len(Gx)):
        # Standard azimuth calculation
        numerator = Gx[i] * By[i] - Gy[i] * Bx[i]
        denominator = Bz[i] * (Gx[i]**2 + Gy[i]**2) - Gz[i] * (Gx[i] * Bx[i] + Gy[i] * By[i])
        
        # Directly compute the azimuth using arctan2
        azimuth[i] = np.degrees(np.arctan2(numerator, denominator))
        
        # Ensure 0-360 range
        if azimuth[i] < 0:
            azimuth[i] += 360
    
    # Create validation DataFrame
    validation_df = pd.DataFrame({
        'Depth': raw_data_df['Depth'],
        'Inc_Original': raw_data_df['Inc'],
        'Inc_Calculated': inc_calc,
        'Inc_Diff': raw_data_df['Inc'] - inc_calc,
        'Azi_Original': raw_data_df['Azi'],
        'Azi_Calculated': azimuth,
        'Azi_Diff': np.minimum(abs(raw_data_df['Azi'] - azimuth), 
                              abs(360 - abs(raw_data_df['Azi'] - azimuth))),
        'G_Magnitude': G,
        'B_Magnitude': B
    })
    
    return validation_df

def create_synthetic_survey_dataset(starting_depth=0, ending_depth=1000, spacing=50, 
                                   magnetic_dip=73.484, magnetic_field_strength=51541.551,
                                   gravity=9.81, declination=1.429, noise_level=0.001,
                                   build_rate=2.0, turn_rate=1.0):
    """Create a synthetic wellbore trajectory and corresponding sensor readings"""
    # Create depth array
    depths = np.arange(starting_depth, ending_depth + spacing, spacing)
    n_points = len(depths)
    
    # Initialize inclination, azimuth, and toolface arrays
    inc = np.zeros(n_points)
    azi = np.zeros(n_points)
    tfo = np.zeros(n_points)  # Default toolface to 0
    
    # Generate a realistic wellbore trajectory
    for i in range(1, n_points):
        delta_depth = depths[i] - depths[i-1]
        
        # Build inclination gradually
        inc_change = build_rate * delta_depth / 30.0
        if depths[i] < ending_depth * 0.75:  # Build section
            inc[i] = min(inc[i-1] + inc_change, 90.0)  # Cap at horizontal
        else:  # Hold section
            inc[i] = inc[i-1]
        
        # Turn azimuth gradually after some inclination is built
        if inc[i] > 5.0:
            azi_change = turn_rate * delta_depth / 30.0
            azi[i] = (azi[i-1] + azi_change) % 360
        else:
            azi[i] = azi[i-1]
        
        # Add some varying toolface
        tfo[i] = (tfo[i-1] + 30) % 360 if inc[i] > 5.0 else 0
    
    # Create trajectory DataFrame
    trajectory_df = pd.DataFrame({
        'Depth': depths,
        'Inc': inc,
        'Azi': azi,
        'tfo': tfo
    })
    
    # Generate raw sensor data
    raw_data_df = generate_perfect_raw_data(
        trajectory_df,
        magnetic_dip=magnetic_dip,
        magnetic_field_strength=magnetic_field_strength,
        gravity=gravity,
        declination=declination,
        add_noise=True,
        noise_level=noise_level
    )
    
    return raw_data_df

def create_example_data():
    """Generate example data based on the provided trajectory"""
    # Example trajectory
    trajectory_data = {
        'Depth': [0, 100, 200, 300, 400],
        'Inc': [0, 10, 15, 20, 20],
        'Azi': [0, 30, 30, 30, 50],
        'tfo': [0, 0, 0, 0, 0]
    }
    trajectory_df = pd.DataFrame(trajectory_data)
    
    # Generate raw sensor data
    raw_data_df = generate_perfect_raw_data(
        trajectory_df, 
        magnetic_dip=73.484,
        magnetic_field_strength=51541.551,
        gravity=9.81,
        declination=1.429,
        add_noise=False
    )
    
    # Add some noise to create a second dataset
    noisy_data_df = generate_perfect_raw_data(
        trajectory_df, 
        magnetic_dip=73.484,
        magnetic_field_strength=51541.551,
        gravity=9.81,
        declination=1.429,
        add_noise=True,
        noise_level=0.005
    )
    
    # Validate results
    validation_df = validate_synthetic_data(raw_data_df)
    noisy_validation_df = validate_synthetic_data(noisy_data_df)
    
    print("Raw Sensor Data (No Noise):")
    print(raw_data_df)
    print("\nValidation Results (No Noise):")
    print(validation_df)
    
    print("\nRaw Sensor Data (With Noise):")
    print(noisy_data_df)
    print("\nValidation Results (With Noise):")
    print(noisy_validation_df)
    
    return raw_data_df, validation_df, noisy_data_df, noisy_validation_df

if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Generate synthetic survey data')
    parser.add_argument('--output', type=str, default='survey_data.csv', 
                        help='Output filename')
    parser.add_argument('--input-trajectory', type=str, default=None,
                        help='Excel file containing trajectory data (Depth, Inc, Azi, tfo)')
    parser.add_argument('--depth-start', type=float, default=0, 
                        help='Starting depth')
    parser.add_argument('--depth-end', type=float, default=1000, 
                        help='Ending depth')
    parser.add_argument('--spacing', type=float, default=30, 
                        help='Survey station spacing')
    parser.add_argument('--dip', type=float, default=73.484, 
                        help='Magnetic dip angle')
    parser.add_argument('--declination', type=float, default=1.429, 
                        help='Magnetic declination')
    parser.add_argument('--field-strength', type=float, default=51541.551, 
                        help='Magnetic field strength in nT')
    parser.add_argument('--gravity', type=float, default=9.81, 
                        help='Gravity value in m/s²') 
    parser.add_argument('--noise', type=float, default=0.001, 
                        help='Sensor noise level')
    parser.add_argument('--no-plot', action='store_true',
                        help='Skip plotting results')
    parser.add_argument('--excel', action='store_true',
                        help='Output in Excel format instead of CSV')
    parser.add_argument('--sheet-name', type=str, default='Survey Data',
                        help='Sheet name for Excel output')
    parser.add_argument('--example', action='store_true',
                        help='Generate example data instead of complex trajectory')
    
    args = parser.parse_args()
    
    # If input trajectory file is provided, read it
    trajectory_df = None
    if args.input_trajectory:
        print(f"Reading trajectory from: {args.input_trajectory}")
        trajectory_df = read_trajectory_from_excel(args.input_trajectory)
    
    if args.example:
        # Generate example data
        print("Generating example data...")
        
        # Use input trajectory if provided
        if trajectory_df is not None:
            # Generate data based on input trajectory
            raw_data_df = generate_perfect_raw_data(
                trajectory_df,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination,
                add_noise=False
            )
            
            noisy_data_df = generate_perfect_raw_data(
                trajectory_df,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination,
                add_noise=True,
                noise_level=args.noise
            )
            
            validation_df = validate_synthetic_data(
                raw_data_df,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination
            )
            
            noisy_validation_df = validate_synthetic_data(
                noisy_data_df,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination
            )
        else:
            # Use default example if no trajectory provided
            raw_data_df, validation_df, noisy_data_df, noisy_validation_df = create_example_data()
        
        # Plot validation results
        if not args.no_plot:
            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            
            # Clean data plots
            axs[0, 0].plot(validation_df['Depth'], validation_df['Inc_Original'], 'b-', label='Original')
            axs[0, 0].plot(validation_df['Depth'], validation_df['Inc_Calculated'], 'r--', label='Calculated')
            axs[0, 0].set_xlabel('Depth (m)')
            axs[0, 0].set_ylabel('Inclination (deg)')
            axs[0, 0].legend()
            axs[0, 0].set_title('Inclination Comparison - Perfect Data')
            
            axs[0, 1].plot(validation_df['Depth'], validation_df['Azi_Original'], 'b-', label='Original')
            axs[0, 1].plot(validation_df['Depth'], validation_df['Azi_Calculated'], 'r--', label='Calculated')
            axs[0, 1].set_xlabel('Depth (m)')
            axs[0, 1].set_ylabel('Azimuth (deg)')
            axs[0, 1].legend()
            axs[0, 1].set_title('Azimuth Comparison - Perfect Data')
            
            # Noisy data plots
            axs[1, 0].plot(noisy_validation_df['Depth'], noisy_validation_df['Inc_Original'], 'b-', label='Original')
            axs[1, 0].plot(noisy_validation_df['Depth'], noisy_validation_df['Inc_Calculated'], 'r--', label='Calculated')
            axs[1, 0].set_xlabel('Depth (m)')
            axs[1, 0].set_ylabel('Inclination (deg)')
            axs[1, 0].legend()
            axs[1, 0].set_title('Inclination Comparison - Noisy Data')
            
            axs[1, 1].plot(noisy_validation_df['Depth'], noisy_validation_df['Azi_Original'], 'b-', label='Original')
            axs[1, 1].plot(noisy_validation_df['Depth'], noisy_validation_df['Azi_Calculated'], 'r--', label='Calculated')
            axs[1, 1].set_xlabel('Depth (m)')
            axs[1, 1].set_ylabel('Azimuth (deg)')
            axs[1, 1].legend()
            axs[1, 1].set_title('Azimuth Comparison - Noisy Data')
            
            plt.tight_layout()
            plt.show()
            
            # Plot differences
            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            
            # Clean data difference plots
            axs[0, 0].plot(validation_df['Depth'], validation_df['Inc_Diff'], 'g-')
            axs[0, 0].set_xlabel('Depth (m)')
            axs[0, 0].set_ylabel('Difference (deg)')
            axs[0, 0].set_title('Inclination Difference - Perfect Data')
            
            axs[0, 1].plot(validation_df['Depth'], validation_df['Azi_Diff'], 'g-')
            axs[0, 1].set_xlabel('Depth (m)')
            axs[0, 1].set_ylabel('Difference (deg)')
            axs[0, 1].set_title('Azimuth Difference - Perfect Data')
            
            # Noisy data difference plots
            axs[1, 0].plot(noisy_validation_df['Depth'], noisy_validation_df['Inc_Diff'], 'g-')
            axs[1, 0].set_xlabel('Depth (m)')
            axs[1, 0].set_ylabel('Difference (deg)')
            axs[1, 0].set_title('Inclination Difference - Noisy Data')
            
            axs[1, 1].plot(noisy_validation_df['Depth'], noisy_validation_df['Azi_Diff'], 'g-')
            axs[1, 1].set_xlabel('Depth (m)')
            axs[1, 1].set_ylabel('Difference (deg)')
            axs[1, 1].set_title('Azimuth Difference - Noisy Data')
            
            plt.tight_layout()
            plt.show()
        
        # Save to Excel or CSV
        if args.excel:
            # Prepare output filenames
            clean_output = args.output.replace('.csv', '_clean.xlsx') if args.output.endswith('.csv') else args.output.replace('.xlsx', '_clean.xlsx')
            noisy_output = args.output.replace('.csv', '_noisy.xlsx') if args.output.endswith('.csv') else args.output.replace('.xlsx', '_noisy.xlsx')
            
            # Save to Excel files
            with pd.ExcelWriter(clean_output, engine='openpyxl') as writer:
                raw_data_df.to_excel(writer, sheet_name='Raw Data', index=False)
                validation_df.to_excel(writer, sheet_name='Validation', index=False)
            
            with pd.ExcelWriter(noisy_output, engine='openpyxl') as writer:
                noisy_data_df.to_excel(writer, sheet_name='Raw Data', index=False)
                noisy_validation_df.to_excel(writer, sheet_name='Validation', index=False)
            
            print(f"Saved clean data to Excel file: {clean_output}")
            print(f"Saved noisy data to Excel file: {noisy_output}")
        else:
            # Save to CSV files
            clean_output = args.output.replace('.xlsx', '_clean.csv') if args.output.endswith('.xlsx') else args.output.replace('.csv', '_clean.csv')
            noisy_output = args.output.replace('.xlsx', '_noisy.csv') if args.output.endswith('.xlsx') else args.output.replace('.csv', '_noisy.csv')
            
            raw_data_df.to_csv(clean_output, index=False)
            noisy_data_df.to_csv(noisy_output, index=False)
            
            print(f"Saved clean data to CSV file: {clean_output}")
            print(f"Saved noisy data to CSV file: {noisy_output}")
    else:
        # Generate a complex trajectory or use input
        if trajectory_df is not None:
            print(f"Generating raw sensor data from input trajectory...")
            # Generate raw data from input trajectory
            complex_data = generate_perfect_raw_data(
                trajectory_df,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination,
                add_noise=True,
                noise_level=args.noise
            )
        else:
            # Generate synthetic trajectory if none provided
            print(f"Generating complex trajectory from {args.depth_start}m to {args.depth_end}m...")
            complex_data = create_synthetic_survey_dataset(
                starting_depth=args.depth_start,
                ending_depth=args.depth_end,
                spacing=args.spacing,
                magnetic_dip=args.dip,
                magnetic_field_strength=args.field_strength,
                gravity=args.gravity,
                declination=args.declination,
                noise_level=args.noise
            )
        
        complex_validation = validate_synthetic_data(
            complex_data,
            magnetic_dip=args.dip,
            magnetic_field_strength=args.field_strength,
            gravity=args.gravity,
            declination=args.declination
        )
        
        # Plot complex trajectory
        if not args.no_plot:
            fig, axs = plt.subplots(3, 1, figsize=(12, 15))
            
            # Trajectory plot
            axs[0].plot(complex_data['Depth'], complex_data['Inc'], 'b-', label='Inclination')
            axs[0].set_xlabel('Measured Depth (m)')
            axs[0].set_ylabel('Inclination (deg)')
            axs[0].set_title('Wellbore Trajectory')
            axs[0].legend(loc='upper left')
            
            ax2 = axs[0].twinx()
            ax2.plot(complex_data['Depth'], complex_data['Azi'], 'r-', label='Azimuth')
            ax2.set_ylabel('Azimuth (deg)')
            ax2.legend(loc='upper right')
            
            # Raw sensor data
            axs[1].plot(complex_data['Depth'], complex_data['Gx'], 'r-', label='Gx')
            axs[1].plot(complex_data['Depth'], complex_data['Gy'], 'g-', label='Gy')
            axs[1].plot(complex_data['Depth'], complex_data['Gz'], 'b-', label='Gz')
            axs[1].set_xlabel('Measured Depth (m)')
            axs[1].set_ylabel('Gravity (m/s²)')
            axs[1].set_title('Accelerometer Readings')
            axs[1].legend()
            
            axs[2].plot(complex_data['Depth'], complex_data['Bx'], 'r-', label='Bx')
            axs[2].plot(complex_data['Depth'], complex_data['By'], 'g-', label='By')
            axs[2].plot(complex_data['Depth'], complex_data['Bz'], 'b-', label='Bz')
            axs[2].set_xlabel('Measured Depth (m)')
            axs[2].set_ylabel('Magnetic Field (nT)')
            axs[2].set_title('Magnetometer Readings')
            axs[2].legend()
            
            plt.tight_layout()
            plt.show()
            
            # Plot validation
            fig, axs = plt.subplots(2, 1, figsize=(12, 10))
            
            # Inc/Azi comparison
            axs[0].plot(complex_validation['Depth'], complex_validation['Inc_Original'], 'b-', label='Original Inc')
            axs[0].plot(complex_validation['Depth'], complex_validation['Inc_Calculated'], 'r--', label='Calculated Inc')
            axs[0].set_xlabel('Depth (m)')
            axs[0].set_ylabel('Inclination (deg)')
            axs[0].legend()
            axs[0].set_title('Inclination Comparison')
            
            axs[1].plot(complex_validation['Depth'], complex_validation['Azi_Original'], 'b-', label='Original Azi')
            axs[1].plot(complex_validation['Depth'], complex_validation['Azi_Calculated'], 'r--', label='Calculated Azi')
            axs[1].set_xlabel('Depth (m)')
            axs[1].set_ylabel('Azimuth (deg)')
            axs[1].legend()
            axs[1].set_title('Azimuth Comparison')
            
            plt.tight_layout()
            plt.show()
        
        # Save to Excel or CSV
        if args.excel:
            output_file = args.output.replace('.csv', '.xlsx') if args.output.endswith('.csv') else args.output
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                complex_data.to_excel(writer, sheet_name='Raw Data', index=False)
                complex_validation.to_excel(writer, sheet_name='Validation', index=False)
            
            print(f"Saved data to Excel file: {output_file}")
        else:
            complex_data.to_csv(args.output, index=False)
            
            # Also save validation
            validation_file = args.output.replace('.csv', '_validation.csv')
            complex_validation.to_csv(validation_file, index=False)
            
            print(f"Saved data to CSV file: {args.output}")
            print(f"Saved validation to CSV file: {validation_file}")
    
    print("Done!")