import os
import shutil
import re
import pandas as pd
from numpy import savetxt, array
import glob 
import xarray as xr
import gc

def backup_file(file_path):
    """
    Creates a backup of the specified file.
    
    Args:
        file_path (str): Path to the file to backup.
    
    Returns:
        str: Path to the backup file.
    """
    backup_path = f"{file_path}.bak"
    shutil.copy(file_path, backup_path)
    print(f"\n\nBackup created at {backup_path}\n\n") # Spaces
    return backup_path

def comment_out_parameters(file_path, variable_names):
    """
    Comments out lines in the file that contain "parameter (variable_name =".

    Args:
        file_path (str): Path to the file to modify.
        variable_names (list): List of variable names to target.

    Returns:
        int: Number of lines commented out.
    """
    lines_commented = 0
    modified_lines = []

    # Compile regex patterns for each variable to match lines like "parameter (variable_name = ..."
    patterns = [re.compile(rf'\bparameter\s*\(\s*{re.escape(var)}\s*=') for var in variable_names]

    try:
        with open(file_path, 'r') as file:
            for line in file:
                line_modified = False
                for pattern in patterns:
                    if pattern.search(line):
                        # Check if the line is already commented
                        if not line.lstrip().startswith('!'):
                            modified_line = f"!{line}"
                            modified_lines.append(modified_line)
                            lines_commented += 1
                            print(f"Commented out line: {line.strip()}")
                            line_modified = True
                            break  # No need to check other patterns
                if not line_modified:
                    modified_lines.append(line)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' does not exist.")
        return lines_commented
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return lines_commented

    try:
        with open(file_path, 'w') as file:
            file.writelines(modified_lines)
        print(f"Total lines commented out: {lines_commented}")
    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")
    return lines_commented

def comment_out_parameters(file_path, variable_names):
    """
    Comments out lines in the file that contain "parameter (variable_name =".

    Args:
        file_path (str): Path to the file to modify.
        variable_names (list): List of variable names to target.

    Returns:
        int: Number of lines commented out.
    """
    lines_commented = 0
    modified_lines = []

    # Compile regex patterns for each variable to match lines like "parameter (variable_name = ..."
    patterns = [re.compile(rf'\bparameter\s*\(\s*{re.escape(var)}\s*=') for var in variable_names]

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line_modified = False
                for pattern in patterns:
                    if pattern.search(line):
                        # Check if the line is already commented
                        if not line.lstrip().startswith('!'):
                            modified_line = f"!{line}"
                            modified_lines.append(modified_line)
                            lines_commented += 1
                            print(f"Commented out line: {line.strip()}")
                            line_modified = True
                            break  # No need to check other patterns
                if not line_modified:
                    modified_lines.append(line)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' does not exist.")
        return lines_commented
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return lines_commented

    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(modified_lines)
        print(f"Total lines commented out: {lines_commented}")
    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")

    return lines_commented

def scale_values(values, min_val, max_val):
    """
    Scales input values from a normalized range [0, 1] to a specified range [min_val, max_val].
    
    Raises:
        ValueError: If 'values' contains non-numeric data.
    """
    if not pd.api.types.is_numeric_dtype(values):
        raise ValueError("Input 'values' must be numeric.")
    return values * (max_val - min_val) + min_val

def save_in_batches(batch_data, batch_paths):
    """
    Save a batch of DataFrames (like meterological input files after adding runoff) to disk.

    Args:
    - batch_data (list of DataFrames): List of DataFrames to save.
    - batch_paths (list of str): Corresponding filenames for the batch.
    """
    for data, name in zip(batch_data, batch_paths):
        savetxt(name, data, fmt='%2.3f', delimiter='\t')
    print(f"Saved batch: {batch_paths}")

# Pull the trial number from the file name 
def get_trial_id(fname):
    base = os.path.basename(fname)
    try:
        return int(os.path.splitext(base)[0].split("-")[-1])
    except (IndexError, ValueError):
        print(f"Failed to extract run number from: {fname}")
        return None

# Build DataArray and dimensions for each variable 
def build_netCDF(path, file_pattern, var_name):

    MET_UNITS = {
        "T2M": "degK",
        "D2M": "degK",
        "WIND": "m/s",
        "SSRD": "W/m^2",
        "STRD": "W/m^2",
        "SP": "Pa",
        "TP": "mm",
        "RUNOFF": "mm",
        "d18OP": "per mil",
        "d18OR": "per mil",
        "d2HP": "per mil",
        "d2HR": "per mil",
        "ACC": "mm",
        "d18OACC": "per mil",
        "d2HACC": "per mil",
    }

    SURFACE_UNITS = {
        "tlake": "degC",
        "fice": "fractional units",
        "hice": "m",
        "hsnow": "m",
        "evap": "mm/day",
        "lakelev": "m", 
        "discharge": "m^3/day",
        "mix": "m", 
        "d18O": "per mil", 
        "d2H": "per mil",
        # Other variables may be output by the user... 
    }

    filepaths = sorted(
        glob.glob(os.path.join(path, file_pattern)),
        key=get_trial_id,
    )

    if not filepaths:
        print(f"No files found for pattern {file_pattern} in {path}")
        return None

    dataarrays = []

    for i, f in enumerate(filepaths):
        trial = get_trial_id(f)
        if trial is None:
            continue
        
        # Read in each df 
        if file_pattern == "met-input-*.txt":
            df = pd.read_csv(f, header=None, delimiter='\t')
            df.columns = ["YEAR", "MON", "DAY", "T2M", "D2M", "WIND", "SSRD", "STRD",
                          "SP", "TP", "RUNOFF", "d18OP", "d18OR", "d2HP", "d2HR", "ACC", "d18OACC", "d2HACC"]
        else: 
            df = pd.read_csv(f, skiprows=0, header=0, sep=r"\s+")

        if file_pattern == "met-input-*.txt":
            # Ensure YEAR, MON, and DAY columns are integers
            df[['YEAR', 'MON', 'DAY']] = df[['YEAR', 'MON', 'DAY']].astype(int)

            # Convert calendar days to datetime format
            try:
                time = pd.to_datetime(
                    df[['YEAR', 'MON', 'DAY']].astype(str).agg('-'.join, axis=1),
                    format='%Y-%m-%d'
                )
            except ValueError as e:
                print(f"Error processing calendar day file {f}: {e}")
                continue

        else:
            # Process other files
            df = pd.read_csv(f, skiprows=0, header=0, sep=r'\s+')

            # Ensure YEAR, MON, and DAY columns are integers
            df[['YEAR', 'MON', 'DAY']] = df[['YEAR', 'MON', 'DAY']].astype(int)

            # Convert Julian days to datetime format
            try:
                time = pd.to_datetime(
                    df[['YEAR', 'MON', 'DAY']].astype(str).agg('-'.join, axis=1),
                    format='%Y-%m-%j'
                )
            except ValueError:
                time = pd.to_datetime(
                    df[['YEAR', 'MON', 'DAY']].astype(str).agg('-'.join, axis=1),
                    format='%Y-%m-%d'
                )
        
        var_cols = [c for c in df.columns if c not in ["YEAR", "MON", "DAY"]]
        variable = array(var_cols, dtype=str) 

        vals = df[var_cols].to_numpy()

        # Set up the DataArray
        da = xr.DataArray(
            data=vals,
            coords={"time": time, "variable": variable},
            dims=("time", "variable"),
            name=var_name,
        ).expand_dims(trial=[trial])

        # Assign the units for non-profile variables
        if var_name == "met":
            unit_list = [MET_UNITS.get(v, "unknown") for v in variable]
            da = da.assign_coords(units=("variable", unit_list))

        elif var_name == "surface":
            unit_list = [SURFACE_UNITS.get(v, "unknown") for v in variable]
            da = da.assign_coords(units=("variable", unit_list))

        dataarrays.append(da)
    
        # free as much as possible before the next file
        del df, vals
        gc.collect()

    # concat all trials, then reorder dims so time is first
    da_all = xr.concat(dataarrays, dim="trial")
    da_all = da_all.transpose("time", "variable", "trial") # Make time the index for plotting easier 
    
    return da_all