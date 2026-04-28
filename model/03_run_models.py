# %% Parallel instances of lake model
import os
import shutil
import subprocess
import threading
import logging
from helper_functions import *
import time 

# Note program start time
start_time = time.time()

# Configure logging
logging.basicConfig(
    filename='lake_execution.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def run_lake_with_semaphore(semaphore, subfolder, exec_dir, output_dir):
    with semaphore:
        subfolder_path = os.path.join(exec_dir, subfolder)
        try:
            # force 'lake' executable to have execute permissions
            lake_exec = os.path.join(subfolder_path, 'lake')
            if not os.path.isfile(lake_exec):
                error_msg = f"'lake' executable not found in {subfolder_path}"
                logging.error(error_msg)
                print(error_msg)
                return
            
            if not os.access(lake_exec, os.X_OK):
                os.chmod(lake_exec, 0o755)
                logging.info(f"Set execute permissions for {lake_exec}")
            
            # Run the ./lake executable
            logging.info(f"Running lake executable in {subfolder}")
            process = subprocess.Popen(
                ["./lake"],
                cwd=subfolder_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=600)
            
            if process.returncode != 0:
                error_msg = f"Error running model in {subfolder}: {stderr}"
                logging.error(error_msg)
                print(error_msg)
                return
            
            # Check for output files
            output_files = {
                "surface.txt": "surface.txt not found",
                "profile-d2H.txt": "profile-d2H.txt not found",
                "profile-d18O.txt": "profile-d18O.txt not found",
                "profile-laketemp.txt": "profile-laketemp.txt not found"
            }

            for output_file_name, error_msg in output_files.items():
                output_file_path = os.path.join(subfolder_path, output_file_name)
                if not os.path.isfile(output_file_path):
                    logging.error(f"{error_msg} in {subfolder_path}")
                    print(f"{error_msg} in {subfolder_path}")
            
            # Extract the iteration number 'X' from subfolder name 'model_X'
            try:
                file_num = subfolder.split('_')[1]
            except IndexError:
                file_num = "unknown"
                logging.warning(f"Could not extract number from subfolder name '{subfolder}'")

            rename_output_files = {
                "surface.txt": "surface-{file_num}.txt", 
                "profile-d2H.txt": "profile-d2H-{file_num}.txt",
                "profile-d18O.txt": "profile-d18O-{file_num}.txt", 
                "profile-laketemp.txt": "profile-laketemp-{file_num}.txt"
            }

            for output_file_name, template in rename_output_files.items():
                output_file_path = os.path.join(subfolder_path, output_file_name)

                new_file = template.format(file_num=file_num)
                renamed_file = os.path.join(subfolder_path, new_file)
                os.rename(output_file_path, renamed_file)
                logging.info(f"Renamed output files in {subfolder}")

                # Move the renamed files to the centralized output directiories ('surface' and 'profiles')
                shutil.move(renamed_file, os.path.join(output_dir, new_file))
                logging.info(f"Moved output files from {subfolder} to centralized directories")
            
            success_msg = f"Successfully ran model in {subfolder}"
            logging.info(success_msg)
            print(success_msg)
            
        except subprocess.TimeoutExpired:
            error_msg = f"Timeout running model in {subfolder}"
            logging.error(error_msg)
            print(error_msg)
        except Exception as e:
            error_msg = f"Exception running model in {subfolder}: {e}"
            logging.error(error_msg)
            print(error_msg)

def main():
    # Get the directory where this Python script is located (~/lake-parallel/model/)
    working_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define directories
    exec_dir = os.path.join(working_dir, "archive/lake model exec")
    
    parent_dir = os.path.dirname(working_dir) # Move up one level 
    output_dir = os.path.join(parent_dir, "output") # Make the 'output' folder to hold model results
    
    # Ensure the exec_dir exists
    if not os.path.isdir(exec_dir):
        logging.error(f"The directory '{exec_dir}' does not exist.")
        print(f"Error: The directory '{exec_dir}' does not exist. Please check the path.")
        return
    
    # Get list of model_X subfolders, sorted numerically
    try:
        subfolders = sorted(
            [f for f in os.listdir(exec_dir) if f.startswith("model_") and os.path.isdir(os.path.join(exec_dir, f))],
            key=lambda x: int(x.split('_')[1])  # Sort by the number after 'model_'
        )
    except ValueError as ve:
        logging.error(f"Error sorting subfolders: {ve}")
        print(f"Error sorting subfolders: {ve}")
        return
    
    if not subfolders:
        logging.warning(f"No subfolders found in '{exec_dir}' matching 'model_X'.")
        print(f"No subfolders found in '{exec_dir}' matching 'model_X'.")
        return
    
    logging.info(f"Starting execution of {len(subfolders)} models with up to 5 running in parallel.")
    print(f"Starting execution of {len(subfolders)} models with up to 5 running in parallel.")
    
    # Set number of parallel processes
    semaphore = threading.Semaphore(5)
    
    threads = []
    for subfolder in subfolders:
        thread = threading.Thread(
            target=run_lake_with_semaphore,
            args=(semaphore, subfolder, exec_dir, output_dir)
        )
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()

    # Note program end time
    end_time = time.time()
    # Calculate total run time
    elapsed_time = end_time - start_time
    print(f"Runtime: {elapsed_time:.2f} seconds")
# %%
