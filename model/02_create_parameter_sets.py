############# Set up parameter sets ##################
# This Python script generates parameter sets using Latin Hypercube sampling, runs the runoff model,
# and sets up the lake executables for each parameter set so they can be run later.
# Created by Gerard A. Otiniano
# Adapted by Rebecca G. Topness

# Import packages
import argparse
from pandas import read_csv, DataFrame
from scipy.stats import qmc
import os
import shutil
import subprocess
import numpy as np
from helper_functions import backup_file, comment_out_parameters, scale_values, save_in_batches
from runoff_model import calculate_runoff
import time
import glob
import pdb

# Note program start time
start_time = time.time()

def main(n_it = None, has_params = None, my_params_filename = None, batch_size = 10):
    """
    Function to facilitate parallel instances of the Thomas-group lake model. Requires the "input_parameters.csv" 
    file to be located in the '01_set_up_files' directory. "input_parameters.csv" should be filled in with the parameter 
    names alongside their lower and upper limits. 

    Parameters
    ----------
    n_it : int
        Number of iterations of each variable that should be created by the Latin Hypercube, i.e., number of rows.
    my_params_file_name: str
        Name of a .csv with already created parameter sets, where columns are trial and parameter names. Useful for post-calibration runs. 
    batch_size: int
        Number of meteorlogical input files to be saved to disk at a time. 
    """
    
    # Get the directory where this Python script is located (~/lake-parallel/model/)
    working_dir = os.path.dirname(os.path.abspath(__file__))  

    # If you're generating new parameter sets using Latin Hypercube sampling: 
    if has_params is None: 
        has_params = input("Do you already have parameter sets? (Y/N): ").strip() # .strip gets rid of spaces the user might accidentally type in

        if has_params == 'N': 

            if n_it is None:
                n_it = int(input("Enter number of requested model iterations: "))
            
            # Get the path of the input_parameters.csv file
            input_params_path = os.path.join(working_dir, "01_set_up_files/input_parameters.csv") # Must be named input_parameters.csv
            if not os.path.exists(input_params_path):
                print(f"Error: '{input_params_path}' does not exist.")
                return

            df = read_csv(input_params_path)
            variables = df.param_name.tolist()  # Set parameter names as a list
            
            # Create Latin hypercube
            sampler = qmc.LatinHypercube(d=len(variables), optimization="random-cd", seed = 65) # Setting a seed so I can use same LHS for both lakes
            sample = sampler.random(n=n_it)
            sample = DataFrame(sample, columns=variables)

            # Scale Latin hypercube values to user-given ranges
            for var in variables:
                range_min = df.loc[df.param_name == var, 'min_value'].values
                range_max = df.loc[df.param_name == var, 'max_value'].values
                if len(range_min) == 0 or len(range_max) == 0:
                    print(f"Error: Parameter '{var}' does not have defined min or max values.")
                    continue
                range_min = range_min[0]
                range_max = range_max[0]
                sample[var] = scale_values(sample[var], range_min, range_max)

            # If modeling isotopes, add the d2Ha parameter, based on Global Meteoric Water Line relationship with d2H
            if 'd18Oa' in sample.columns: 
                sample['d2Ha'] = sample['d18Oa'] * 8 + 10
                variables.append('d2Ha')  # Add d2Ha to the list of variables

            # Save 'sample', which holds the parameter names and their tested values over n_it model runs
            sample['trial'] = np.arange(0, len(sample))
            sample.to_csv(os.path.join(working_dir, 'parameter_values_tested.csv'), index = False) # Save the parameter sets that were actually used

        # If you already have parameter sets you want to test: 
        elif has_params == 'Y': 
            my_params_filename = input("Enter the file name (e.g., my_parameter_sets.csv): ").strip()
            setup_dir = os.path.join(working_dir, "01_set_up_files") # set-up directory
            if not os.path.exists(setup_dir):
                print(f"Error: '{setup_dir}' does not exist.")
                return
            
            input_params_path = os.path.join(setup_dir, my_params_filename)   
            
            if not os.path.exists(input_params_path):
                print(f"Error: '{input_params_path}' does not exist.")
                return

            sample = read_csv(input_params_path)
            variables = sample.columns.to_list()
            n_it = len(sample)
        
        else: 
            print('Please enter Y or N.')
            return

    # Identify lake parameters and runoff parameters
    # All possible lake parameters to test 
    lake_params = ['cdrn', 'eta', 'alb_snow', 'alb_slush', 'd18Oa', 'd2Ha', 'f', 'alb_sed', 'csed', 'consed']
    # All possible runoff parameters to test
    runoff_params = ['melt_ratio', 'rsm_ratio', 'p', 's', 'thaw_threshold',  'freeze_threshold', 
                        'rp_ratio_freeze', 'rp_ratio_cold', 'rp_ratio_mild', 'rp_ratio_warm', 
                        'glacier_flux', 'glacier_2H', 'glacier_18O']

    # Filter variables into their respective categories 
    lake_variables = [var for var in variables if var in lake_params]
    runoff_variables = [var for var in variables if var in runoff_params]

    # Get the lake.inc.save template that will change with each parameter set for the executable
    template_path = os.path.join(working_dir, '01_set_up_files/lake.inc.save')
    #pdb.set_trace()

    if not os.path.exists(template_path):
        print(f"Error: '{template_path}' does not exist.")
        return

    backup_file(template_path)
    lines_commented = comment_out_parameters(template_path, lake_variables) # Only comment out lake variables in lake.inc that are varying in the LHS
    
    # Prepare 'lake parameters' directory
    prop_param_dir = os.path.join(working_dir, "archive/lake parameters") # Moved all these files users don't need to look at into 'archive'
    if os.path.exists(prop_param_dir):
        shutil.rmtree(prop_param_dir)
    os.makedirs(prop_param_dir, exist_ok=True)
    param_dir = prop_param_dir  # Assign the path directly

    # Prepare 'met files' directory 
    prop_met_dir = os.path.join(working_dir, "archive/met files")
    if os.path.exists(prop_met_dir):
        shutil.rmtree(prop_met_dir)
    os.makedirs(prop_met_dir, exist_ok=True)
    met_dir = prop_met_dir
    
    # Prepare 'lake model exec' directory
    prop_exec_dir = os.path.join(working_dir, "archive/lake model exec")
    if os.path.exists(prop_exec_dir):
        shutil.rmtree(prop_exec_dir)
    os.makedirs(prop_exec_dir, exist_ok=True)
    exec_dir = prop_exec_dir  # Assign the path directly
    
    # Define the 'lake model' directory (where the Fortran subroutines are)
    model_dir = os.path.join(working_dir, "lake model")
    if not os.path.exists(model_dir):
        print(f"Error: '{model_dir}' directory does not exist.")
        return
    
    # Get meterological input file
    set_up_dir = os.path.join(working_dir, '01_set_up_files') # Met input file must be placed in this folder
    if not os.path.exists(set_up_dir):
        print(f"Error: '{set_up_dir}' does not exist.")
        return
    txt_files = glob.glob(os.path.join(set_up_dir, '*.txt')) # Look for .txt files in the folder
    if not txt_files: 
        print(f"Error: No meterological input file found in {set_up_dir}.")
    met_input_file = txt_files[0] # use the first .txt file found in the directory 
    print(f"\n\nUsing meteorlogical input file: {met_input_file}.\n\n")

    # Read in ERA5 data
    met = read_csv(met_input_file, sep='\t', header=None)
    met.columns = ['YEAR', 'MONTH', 'DAY', 'T2M', 'D2M', 'WIND', 'SSRD', 'STRD', 'SP', 'TP', 'd18OP', 'd2HP']

    # Set up temporary storage for writing the meterological input files in batches 
    batch_data = []
    batch_names = []

    # Write meterological input files with isotope and runoff variables using Latin Hypercube values
    for i in range (n_it):

        # Prepare new file path where the modified content will be saved
        new_met_path = os.path.join(met_dir, f"met-input-{i}.txt")

        # Get the set of parameter values from the sample for iteration i
        param_set = sample.iloc[i][runoff_variables].to_dict()

        # Use iteration i parameter set and meterological input file to calculate runoff variables
        met_out = calculate_runoff(param_set, met.copy()) # Use a copy of the meterological input file 

        # Save meterological input files in batches 
        batch_data.append(met_out)
        batch_names.append(new_met_path)

        # Save the batch when it's full or on the last iteration
        if len(batch_data) == batch_size or i == n_it - 1:
            save_in_batches(batch_data, batch_names)
            batch_data.clear()  # Clear the batch data
            batch_names.clear()  # Clear the batch filenames

    # Write all lake.inc files with Latin hypercube values
    for i in range(n_it):
        # Read the template file
        with open(template_path, "r", encoding='utf-8') as template_file:
            template_content = template_file.read()
        
        # Prepare the new file path where the modified content will be saved
        new_file_path = os.path.join(param_dir, f"lake_{i}.inc")  # Save to a different location or name
        
        # Write the template content and the new parameters into the new file
        with open(new_file_path, "w", encoding='utf-8') as new_file:
            # Write the template content first
            new_file.write(template_content)
            
            # Append the parameters (j) from 'sample' for the ith iteration
            for j in lake_variables:
                value = sample.loc[i, j]  # Extract the value from the sample for iteration i
                new_file.write(f"\n      parameter ({j} = {value})")

    # Get all files in the directory that match the pattern "lake_X.inc"
    param_files = sorted(
        [f for f in os.listdir(param_dir) if f.startswith("lake_") and f.endswith(".inc")],
        key=lambda x: int(x.split('_')[1].split('.')[0])  # Sort by number after 'lake_'
    )

    # Get all meteorlogical input files in the directory that match the pattern "met-input-X.txt"
    met_files = sorted(
        [f for f in os.listdir(met_dir) if f.startswith("met-input-") and f.endswith(".txt")],
        key=lambda x: int(x.split('-')[2].split('.')[0])  # Sort by number after 'met-input-'
    )

    # Check if parameter files were found
    if not param_files:
        print(f"No parameter files found in '{param_dir}'. Exiting.")
        return
    
    if not met_files:
        print(f"No met files found in '{met_dir}'. Exiting.")
    
    # Loop over each parameter file
    for param_file in param_files:
        # Extract the number X from the filename
        try:
            file_num = param_file.split('_')[1].split('.')[0]
        except IndexError:
            print(f"Error parsing file number from '{param_file}'. Skipping.")
            continue

        # Copy the parameter file into "lake model/lake.inc"
        src_param_file = os.path.join(param_dir, param_file)
        dst_param_file = os.path.join(model_dir, "lake.inc")
        shutil.copy(src_param_file, dst_param_file)

        # Compile Fortran files
        try:
            f90_files = [f for f in os.listdir(model_dir) if f.endswith(".f90")]
            if not f90_files:
                print(f"No .f90 files found in {model_dir}. Skipping {param_file}.")
                continue
            # Compile each .f90 file
            compile_command = ["gfortran", "-c"] + f90_files
            subprocess.run(compile_command, cwd=model_dir, check=True)

            # Link object files to create the executable
            o_files = [f for f in os.listdir(model_dir) if f.endswith(".o")]
            if not o_files:
                print(f"No .o files found after compilation in {model_dir}. Skipping {param_file}.")
                continue
            link_command = ["gfortran", "-o", "lake"] + o_files
            subprocess.run(link_command, cwd=model_dir, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error during gfortran compilation for {param_file}: {e}. Skipping.")
            continue

        # Create a subfolder in "lake model exec" called "model_X"
        subfolder_name = f"model_{file_num}"
        subfolder_path = os.path.join(exec_dir, subfolder_name)
        os.makedirs(subfolder_path, exist_ok=True)

        # Copy the executable "lake" to the subfolder
        lake_exec = os.path.join(model_dir, "lake")
        
        if not os.path.isfile(lake_exec):
            print(f"Executable 'lake' not found in '{model_dir}'. Skipping {param_file}.")
            continue
        
        shutil.copy(lake_exec, subfolder_path)

        # Find "met-input-X.txt" that matches the current subfolder 
        matching_met_file = f"met-input-{file_num}.txt"
        met_file_path = os.path.join(met_dir, matching_met_file)
        if os.path.isfile(met_file_path):
            # Copy "met-input-X.txt" to the subfolder
            shutil.copy(met_file_path, os.path.join(subfolder_path, "met-input.txt"))
        else:
            print(f"Error: '{matching_met_file} not found in '{met_dir}. Skipping.")

        print(f"Copied {matching_met_file} to {subfolder_path}/met-input.txt")

        # Delete all ".o" files in "lake model"
        for obj_file in os.listdir(model_dir):
            if obj_file.endswith(".o"):
                try:
                    os.remove(os.path.join(model_dir, obj_file))
                except Exception as e:
                    print(f"Error deleting '{obj_file}' in '{model_dir}': {e}")

        print(f"Processed parameter file: {param_file}, and created executable in '{subfolder_path}'")
    
    # Restore original lake.inc.save file
    backup_path = f"{template_path}.bak"
    if os.path.exists(backup_path):
        try:
            os.remove(template_path)  # Remove the modified lake.inc.save
            shutil.move(backup_path, template_path)  # Rename backup to original
            print(f"Restored original '{template_path}' from backup.")
        except Exception as e:
            print(f"Error restoring backup: {e}")
    else:
        print(f"No backup found at '{backup_path}'. Unable to restore original file.")

    # Move all the met-files to the output directory for easier access later
    parent_dir = os.path.dirname(working_dir) # Move up one level 
    output_dir = os.path.join(parent_dir, "output") # Make the 'output' folder to hold model results
    os.makedirs(output_dir, exist_ok=True)
    for met_file in os.listdir(met_dir):
        shutil.copy(os.path.join(met_dir, met_file), os.path.join(output_dir, met_file))
    print(f"Copied all met-files to '{output_dir}'.")

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Facilitate parallel instances of the Thomas-group lake model using Latin hypercube sampling."
    )
    parser.add_argument(
        "--n_it",
        type=int,
        default=None,
        help="Number of iterations"
    )
    parser.add_argument(
        "--has_params",
        type=str,
        default=None,
        help="Y/N if parameter sets already exist."
    )
    parser.add_argument(
        "--my_params_filename",
        type=str,
        default=None,
        help="Name of .csv file with existing parameter sets."
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=10,
        help="Number of met-files in batch to save (default: 10)"
    )

    # Parse the arguments
    args = parser.parse_args()
    
    # Call the main function with parsed arguments
    main(n_it=args.n_it, has_params=args.has_params, my_params_filename=args.my_params_filename, batch_size=args.batch_size)

    # Note program end time
    end_time = time.time()
    # Calculate total run time
    elapsed_time = end_time - start_time
    print(f"Runtime: {elapsed_time:.2f} seconds")