# Lake proxy system model calibration framework <br> (PRYSM v2.0)

Lake proxy system models (PSMs) are tools for mechanistically interpreting paleoclimate proxy data from lake sediments. The first step in using the PSM is calibrating the Environment submodel (lake model). This framework in Python walks through running and calibrating the Environment submodel of the PRYSM v2.0 framework (Dee et al., 2018).

The lake model is based on Hostetler & Bartlein (1990), with adaptions from Morrill et al. (2019) and Topness et al. (in prep). For a complete description of the model, see Topness et al. (in prep).

## Highlights:
* :grey_question: **Uncertain parameters**: Test different model parameter combinations using Latin Hypercube sampling.
  
* :twisted_rightwards_arrows: **Parallel processing**: Models are run in parallel (default is 5 models run simulaneously), speeding up run times.
  
* :droplet: **Simulate water isotopes**: A runoff-isotope module that can be adapted to any lake is integrated into this framework to provide forcings for lake water and isotope balance.
  
* :white_check_mark: **Calibration**: Example notebooks walk through comparison of model outputs with observations.
___
## How to use this code: 
### (1) Edit the model set-up files located in the `01_set_up_files` folder
* `lake.inc.save`: Defines parameters and sets initial conditions. Edit values in this file that you would like to stay constant throughout your simulations (e.g. lake area by depth from top to bottom, maximum depth, latitude and longtitude, etc.). Descriptions of parameters are commented in the example file in this repository. The name of this file *must* be `lake.inc.save`.
  
* `input_parameters.csv`: Enter parameter names and their range of values (min and max) you wish to test. Parameters not included in this file will stay constant for every simulation at their values defined in `lake.inc.save`. Detailed descriptions of parameters can be found in the `documents` folder and Topness et al. (in prep). The name of this file *must* be `input_parameters.csv`.
  
* Meteorological input file: Model forcing, either from observations, reanalysis data, or climate model output. Must be a .txt file but file name does not matter. See `01_set_up_files` for an example meterological input file on a daily timestep. File columns should be in the following order:

| Variable | Units | 
| ---------- | ---------- |
| Year  |  | 
| Month  |  | 
| Day  | Julian or calendar day | 
| Air temperature | Kelvin or Celcius *See lake.inc.save | 
| Humidity  | Dewpoint (Kelvin or Celcius), relative humidity (%), or specific humidity (kg/kg) *See lake.inc.save | 
| Wind speed  | m/s | 
| Surface indicent shortwave radiation | W/m<sup>2</sup> | 
| Surface downward longwave radiation | W/m<sup>2</sup> | 
| Surface pressure | mb | 
| Total precipitation | mm | 

### (2) Run the `02_create_parameter_sets.py` Python script. This code runs the runoff-isotope module and gets all models ready with parameter sets. 
```
python ./02_create_parameter_sets.py
```
> :information_source: Note: You will be asked if you want to generate a new, user-defined number of parameter sets or use an existing .csv file (i.e., the specific parameter sets that resulted in the best model performance against observations).

### (3) Run the `03_run_models.py` Python script. This will run the models and save outputs in the `output` folder. 
```
python ./03_run_models.py
```
### (4) (Optional) Run the `04_build_netcdfs.py` Python script to aggregate output .txt files from model runs into netCDF files. This is useful for keeping track of 100s-1000s of outputs in one file. 
```
python ./04_build_netcdfs.py
```
Output files are: 
* `lake-model-surface.nc`: All surface.txt files, which contain daily averages of lake surface temperature (deg C), ice fraction (0 to 1), ice thickness (%), snow on ice thickness (m), evaporation (mm/day), lake level (m), discharge (m<sup>3</sup>), maximum mixing depth (# lake layers), and surface water $\delta$<sup>2</sup>H and $\delta$<sup>18</sup>O values (per mil). The variables output in the surface.txt files can be changed in the `lake.inc.save` include file.
  
* `lake-model-met.nc `: Meteorological input files with added columns for runoff amount (mm), precip $\delta$<sup>2</sup>H (per mil), runoff $\delta$<sup>2</sup>H (per mil), precip $\delta$<sup>18</sup>O (per mil), runoff $\delta$<sup>18</sup>O (per mil), accumulated snowfall (mm), accumulation $\delta$<sup>2</sup>H (per mil), accumulated $\delta$<sup>18</sup>O (per mil).
  
* `lake-model-temp.nc`, `lake-model-d2H.nc`, `lake-model-d18O.nc`: Daily average profiles of water temperature, water $\delta$<sup>2</sup>H values, and water <br> $\delta$<sup>18</sup>O values. Column #s are lake layers.

### (5) Calibration
In the `calibration` folder, an example Jupyter notebook `example-lake-psm-calibration.ipynb` demonstrates how a user might evaluate model performance against water temperature and water isotope profile observations using root-mean-square error and visualize results with scatterplots, timeseries, and heatmaps.
___

## References
Dee, S. G., Russell, J. M., Morrill, C., Chen, Z., and Neary, A.: PRYSM v2.0: A Proxy System Model for Lacustrine Archives, Paleoceanogr. Paleoclimatology, 33, 1250–1269, https://doi.org/10.1029/2018PA003413, 2018.  

Hostetler, S. W. and Bartlein, P. J.: Simulation of lake evaporation with application to modeling lake level variations of Harney‐Malheur Lake, Oregon, Water Resour. Res., 26, 2603–2612, https://doi.org/10.1029/WR026i010p02603, 1990. 

Morrill, C., Meador, E., Livneh, B., Liefert, D. T., and Shuman, B. N.: Quantitative model-data comparison of mid-Holocene lake-level change in the central Rocky Mountains, Clim. Dyn., 53, 1077–1094, https://doi.org/10.1007/s00382-019-04633-3, 2019.  

Topness, R. G., Thomas, E. K., Fendrock, M., and Otiniano, G. A.: Calibration guidelines and a runoff-isotope module for lake proxy system modeling (PRYSM v2.0), Geoscientific Model Development, in prep.

https://github.com/carriemorrill/lake-model/tree/lake-model-isotopes
