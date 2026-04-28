# Aggregate lake model output text files into netCDF files per variable
# Rebecca G. Topness 20251118

# Import packages 
from helper_functions import build_netCDF # :)
import os
import xarray as xr
import gc
import pandas as pd

def main():
    # Get the directory where this Python script is located (~/lake-parallel/model/)
    working_dir = os.path.dirname(os.path.abspath(__file__))

    parent_dir = os.path.dirname(working_dir) # Move up one level 
    output_dir = os.path.join(parent_dir, "output") # Make the 'output' folder to hold model results

    # Set up the variables and their file patterns, names, units
    VARIABLE_CONFIG = {
        # Profiles 
        "profile-laketemp": {
            "pattern": "profile-laketemp-*.txt",
            "var_name": "temp",
            "units": "degC",
        },
        "profile-d2H": {
            "pattern": "profile-d2H-*.txt",
            "var_name": "d2H",
            "units": "per mil",
        },
        "profile-d18O": {
            "pattern": "profile-d18O-*.txt",
            "var_name": "d18O",
            "units": "per mil",
        },

        # Multi-variable files 
        "surface": {
            "pattern": "surface-*.txt",
            "var_name": "surface",
            # units assigned already in helper_functions.py
        },
        "met-input": {
            "pattern": "met-input-*.txt",
            "var_name": "met",
            # units assigned already in helper_functions.py

        },
    }

    # Keep track of the profile outputs together
    PROFILE_KEYS = {"profile-laketemp", "profile-d2H", "profile-d18O"}

    for key, cfg in VARIABLE_CONFIG.items():
        file_pattern = cfg["pattern"]
        var_name     = cfg["var_name"]

        print(f"Processing {file_pattern}...")

        da = build_netCDF(output_dir, file_pattern, var_name)
        if da is None:
            print(f"Skipping {key}, build_netCDF returned None")
            continue

        # If it's a profile file (where units are the same for each variable (depth), assign the provided units)
        if var_name in PROFILE_KEYS:
            da.attrs["units"] = cfg["units"]
            # For profiles, make the depth columns numeric
            da = da.assign_coords(variable=pd.to_numeric(da["variable"].values)) #### TRYING THIS, SET 19 JAN
        
        ds = xr.Dataset({var_name: da})

        # Write files
        out_file = os.path.join(output_dir, f"lake-model-{var_name}.nc")
        print(f"Writing {out_file}")
        ds.to_netcdf(out_file)

        # Free memory! before moving to next variable
        del ds, da
        gc.collect()

    print("All outputs processed! :)")

if __name__ == "__main__":
    main()