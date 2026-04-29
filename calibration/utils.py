### Helper functions for calibrating lake model results ###

import pandas as pd
import numpy as np 
import xarray as xr
from scipy.stats import ks_2samp
import matplotlib.pyplot as plt


# Function to prepare model predictions and observations for RMSE calculation #
###############################################################################
def prep_pred_obs(
    sims_ds: xr.Dataset, # model in netcdf format
    obs_df: pd.DataFrame, # observations 
    sims_col: str = "temp", # change for different variables
    obs_col: str = "temperature",
    clamp_surface: bool = True, # in case surface obs really close to the surface 
    clamp_bottom: bool = True, # very deep bottom obs, beyond model resolution
    depth_filter=None, # if you just want to calibrate to one depth 
) -> tuple[xr.DataArray, xr.DataArray, pd.DataFrame]:
    """
    Create arrays of modeled (predicted) and observed (true) values for where they overlap to calculate RMSE/model performance. 
    """
    #### Clean and filter observations ###
    df = obs_df.copy()
    df = df.reset_index() # Reset the index to get datetime as a column

    # Make sure columns are numeric, and drop NaNs
    df = df[['Date', 'Depth', obs_col]].copy()
    df['Date'] = pd.to_datetime(df['Date'], errors="coerce")
    df['Depth'] = pd.to_numeric(df['Depth'], errors="coerce")
    df[obs_col] = pd.to_numeric(df[obs_col], errors="coerce")
    df = df.dropna(subset=['Date', 'Depth', obs_col])

    # Filters for selecting only certain depths
    if depth_filter is not None:
        df = df[depth_filter(df['Depth'])]

    # Flag if there's no observations left 
    if len(df) == 0:
        raise ValueError("No observations left after cleaning/filtering.")

    ### Select the model variable ###
    T = sims_ds[sims_col]

    ### Convert model 'layer count' to midpoints (i.e. model layer 1 = layer 0-1m --> 0.5m) ###
    model_depth_idx = pd.to_numeric(sims_ds['variable'].values) # Model depth is called 'variable', make sure it's numeric 
    T_mid = T.assign_coords({'variable': model_depth_idx - 0.5}).sortby('variable')

    ### Get arrays of obs times/depths ###
    obs_time = df['Date'].values.astype("datetime64[ns]")
    z = df['Depth'].values.astype(float)

    ## Account for obs outside model depth range ##
    # If any observations are shallower than the shallowest model midpoint (0.5m), use 0.5m as their comparison 
    # Probably okay assumption because observations that are 'surface' i.e. 0.08m or something, are close enough to surface
    if clamp_surface:
        zmin = float(T_mid['variable'].min().values)
        z = np.maximum(z, zmin)

    # If any observations are deeper than the deepest model midpoint, use that deepest depth as their comparison
    if clamp_bottom: 
        zmax = float(T_mid['variable'].max().values)
        z = np.minimum(z, zmax)

    ### Get the times/depths that are only neccessary/match observations available ###
    t_unique = np.sort(pd.unique(obs_time)) 
    z_unique = np.unique(z)

    ## Get the times/depths from the model that are only neccessary/match observations available ##
    T_t = T_mid.sel({'time': xr.DataArray(t_unique, dims="time_u")})

    #########################################################################
    # Interpolate lake model predictions to match observation depths 
    T_sub = T_t.interp({'variable': xr.DataArray(z_unique, dims="depth_u")})
    #########################################################################

    ### Map each obs row to indices in reduced arrays ###
    t_index = pd.Index(t_unique).get_indexer(obs_time)
    z_index = np.searchsorted(z_unique, z)

    # Gather model predictions for each observation (new dimension called 'obs')
    pred = T_sub.isel(
        time_u=xr.DataArray(t_index, dims="obs"),
        depth_u=xr.DataArray(z_index, dims="obs"),
    )

    # Ensure output shape is (obs trial)
    pred = pred.transpose("obs", "trial")

    # Get observation values as a DataArray
    true = xr.DataArray(df[obs_col].values.astype(float), dims="obs", name="obs")

    return pred, true


# Function to calculate RMSE, bias, NSE for each trial #
########################################################
def calc_rmse(
    pred: xr.DataArray,
    true: xr.DataArray,
) -> pd.DataFrame:
    """
    Calculate RMSE and other stats for each model trial. 
    """
    # pred dims: (obs, trial); true dims: (obs,)
    err = pred - true
    mse = (err ** 2).mean(dim="obs", skipna=True)
    rmse = np.sqrt(mse)
    bias = err.mean(dim="obs", skipna=True)
    nse = 1 - ( (err ** 2).sum(dim="obs", skipna=True) / ((true - true.mean(dim="obs", skipna=True)) ** 2).sum(dim="obs", skipna=True) )

    # Count how many observations contributed to each calculation 
    n_points = int(np.isfinite(pred.isel({'trial': 0}).values).sum())

    # Return a dataframe with the stats 
    return pd.DataFrame({
        "trial": rmse["trial"].values,
        "rmse": rmse.values,
        "bias": bias.values,
        "nse": nse.values, 
        "n_points": n_points,
    })

# Function to make all profile observations have the same number of obs/equally spaced # 
########################################################################################
def get_equal_profiles(
    obs_df: pd.DataFrame,
    target_depths=(1, 4, 8, 18), # these are the approx. depths we want for each day's profile
) -> pd.DataFrame:
    """
    Get profiles that have an equal amount of observations for each day for the experiments, and the observations 
    are equally spaced through the water column. 
    """

    df = obs_df.copy()

    # Keep track of obs that meet the criteria 
    kept = []

    # Check each day and the obs on that day 
    for day, g in df.groupby('Date', sort=True):
        if len(g) < len(target_depths):
            continue

        remaining = g.copy()
        chosen_rows = []

        for t in target_depths:
            # Take absolute difference of the actual depth relative to the target, the closest depth wins (i.e. 2.0m is closest to 1 if 1.0 absent)
            dist = (remaining['Depth'] - t).abs()

            # idx of closest row
            idx = dist.idxmin()

            row = remaining.loc[idx].copy()
            row["target_depth"] = float(t)
            row["depth_error"] = float(abs(row['Depth'] - t))  # keep track of how far off target it was
            chosen_rows.append(row)

            # Remove so we can't reuse the same observation for another target
            remaining = remaining.drop(index=idx)
            if remaining.empty and len(chosen_rows) < len(target_depths):
                break

        if len(chosen_rows) == len(target_depths):
            kept.append(pd.DataFrame(chosen_rows))

    if not kept:
        return df.iloc[0:0].copy()

    # Put all the chosen depths together
    out = pd.concat(kept, ignore_index=True)

    # Sort within each day
    sort_cols = ['Date', "target_depth"]
    out = out.sort_values(sort_cols).reset_index(drop=True)

    # Return new obs df 
    return out

# Function to get interpolated model values at any depth (avoid having to interpolate every model layer just to visualize a few = too costly) #
###############################################################################################################################################
def get_any_depth(ds, depth = 1.0):
    depth_idx = pd.to_numeric(ds["variable"].values)
    var_mid = ds.assign_coords(variable = depth_idx - 0.5).sortby("variable") # We treat slices as midpoints 
    var_depth = var_mid.interp(variable=depth)
    return var_depth

# Function to check timing of ice-off using the lake-model-surface.nc # 
########################################################################################
def check_iceoff_timing(df):

    # Keep values only where condition is met; else NaN
    masked = df.where(df == 0)

    # Per year, first time condition is met
    first_dates = (
        masked.groupby(masked.index.year)
              .apply(lambda g: g.apply(pd.Series.first_valid_index))
    )
    first_dates.index.name = "year"

    first_dates = first_dates.map(lambda x: pd.NaT if x is None else x).astype("datetime64[ns]")

    # Median day-of-year per column
    median_doy = first_dates.apply(lambda s: s.dt.dayofyear.median(), axis=0).astype(float)

    # Make it a df where columns are trial and median_DOY 
    median_df = (
    pd.DataFrame({
        "trial": pd.to_numeric(median_doy.index, errors="coerce").astype("Int64"),
        "median_DOY": median_doy.values.astype(float),
    })
    .dropna(subset=["trial"]) )

    return median_df

# Make the scatterplot figure # 
########################################################################################
# Use K-S test to see distribution changes 
def fmt_p(p):
    for a in (0.001, 0.01, 0.05):
        if p < a:
            return f"p<{a:g}"
    return f"p={p:.3f}"

# Scatterplot function
def scatterplot_stats_vs_params(stats, params, stat_col = 'rmse', params_list = None, trials_list = None):

    # Count number of best trials 
    best_n = len(trials_list)
    print(f"Number of best trials: {best_n}")

    # List of parameters to plot
    if params_list is None:
        # Lake and runoff parameters 
        params_list = ['eta', 'cdrn', 'alb_slush', 'alb_snow', 'd18Oa', 'd2Ha', 'f', 'melt_ratio', 'rsm_ratio', 'p', 's', 'thaw_threshold', 'freeze_threshold', 
            'rp_ratio_freeze', 'rp_ratio_cold', 'rp_ratio_mild', 'rp_ratio_warm']

    # Calculate the number of rows and columns for the subplots
    n_params = len(params_list)
    n_cols = 4
    n_rows = (n_params + n_cols - 1) // n_cols  # Ensures we have enough rows to cover all parameters

    # Make subplots
    fig, axes = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(10,10))
    axes = axes.flatten()

    # Loop over parameters and plot scatterplots
    for i, param in enumerate(params_list):
        # Scatterplot for all simulations (gray dots)
        axes[i].scatter(stats[param], stats[stat_col], color='lightgray', alpha=0.6)

        # Scatterplot for top # of simulations (black dots)
        good_stats = stats[stats['trial'].isin(trials_list)]
        axes[i].scatter(good_stats[param], good_stats[stat_col], color='k', alpha=0.8)

        axes[i].set_xlabel(param, fontsize = 12)
        axes[i].set_ylabel(stat_col, fontsize = 12)
    
    # Collect and spit out the ranges for all parameters for the best n runs 
        param_min = good_stats[param].min()
        param_max = good_stats[param].max()
        print(f"Parameter: {param}, Min: {param_min:.6f}, Max: {param_max:.6f}")

        # Calculate K-S test between uniform range and validation range for each parameter 
        x = np.asarray(params[param], dtype=float) 
        y = np.asarray(good_stats[param], dtype=float)
        x = x[~np.isnan(x)]
        y = y[~np.isnan(y)]

        # KS test and rounded label
        stat, p = ks_2samp(y, x)               
        label = f"KS={stat:.3f}, {fmt_p(p)}"
    
        # Print the stat and p_value on each plot
        axes[i].text(
            0.05, 0.95, label,
            transform=axes[i].transAxes, ha="left", va="top",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.6", alpha=0)
        )
    
    plt.figtext(0.3, 0.12, f"Best parameter sets n={best_n}", ha="left", fontsize=16, color = 'k')
    plt.figtext(0.3, 0.15, "All parameter sets", ha="left", fontsize=16, color = 'gray')

    # Print average RMSE of the top n runs
    avg_rmse = good_stats[stat_col].mean()
    print(f"Average RMSE of top {best_n} runs: {avg_rmse}")
    min_rmse = good_stats[stat_col].min()
    max_rmse = good_stats[stat_col].max()
    print(f"{min_rmse} - {max_rmse} RMSE range for top {best_n} runs")
    
    # Remove empty subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    plt.tight_layout()

    plt.show()
    
    return fig