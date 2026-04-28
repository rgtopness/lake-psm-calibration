###### Runoff Model #####

# What this code does: adds runoff to the meterological input file 
# iteratively as runoff parameters are assigned through the 
# Latin Hypercube Sampling framework 

# Last updated: Rebecca G. Topness 20250522
# Name: 'Model, Runoff Model'


# Packages
import warnings
import numpy as np
from math import sqrt, pi, exp, ceil
from pandas import DataFrame
import pdb

warnings.simplefilter(action='ignore', category=FutureWarning)
np.seterr(divide='ignore')


def calculate_runoff(params, met):
    """
    Adds runoff to the meterological input file iteratively as runoff parameters are assigned through 
    the Latin Hypercube framework.
    
    Args: 
    met_input_file (str): Path to the meterological input .txt file.
    params (dict): Dictionary of variable names and their Latin Hypercube ranges.

    Returns: 
    met: DataFrame with original met_input_file variables plus new runoff variables.

    """
    # Extract parameter values from the dictionary
    melt_ratio = params['melt_ratio']
    rsm_ratio = params['rsm_ratio']
    p = params['p']
    s = params['s']
    thaw_threshold = params['thaw_threshold']
    freeze_threshold = params['freeze_threshold']
    rp_ratio_freeze = params['rp_ratio_freeze']
    rp_ratio_cold = params['rp_ratio_cold']
    rp_ratio_mild = params['rp_ratio_mild']
    rp_ratio_warm = params['rp_ratio_warm']

    # Changing to NumPy because then everything matches for calculations (deprecation error)
    M_tp = met['TP'].to_numpy()
    M_T2M = met['T2M'].to_numpy()
    M_d18O = met['d18OP'].to_numpy()
    M_d2H = met['d2HP'].to_numpy()

    n_rows = len(met)

    # Set up additional variables to be calculated in the runoff model
    M_acc = np.zeros(n_rows)
    M_runoff = np.zeros(n_rows)
    M_acc_d2H = np.zeros(n_rows)
    M_acc_d18O = np.zeros(n_rows)
    M_runoff_d2H = np.zeros(n_rows)
    M_runoff_d18O = np.zeros(n_rows)

    # Calculate R/P ratios using air temperature 
    #### UPDATE TEMPERATURE THRESHOLDS FOR YOUR SITE ###
    rp_ratios = np.where(
        M_T2M <= 273, rp_ratio_freeze,
        np.where(
            M_T2M <= 278, rp_ratio_cold,
            np.where(M_T2M <= 288, rp_ratio_mild, rp_ratio_warm)
        )
    )

    # =============================================================================
    # =================== Set parameters and scaling factors ======================
    # =============================================================================

    #### COMMENT OUT PARAMETERS YOU WISH TO TEST VIA LATIN HYPERCUBE SAMPLING ###

    #melt_ratio = 0.5  # fraction of acc precip to liquid per time step - ie. how much accumulated snow turns from solid to liquid

    #rsm_ratio = 0.9  # fraction of snowmelt converted to runoff - ie. how much melted snow goes into the lake/turns into runoff

    glacier_flux = 0.  # mm runoff per ha basin area; set to 0 if no glacier in catchment

    #p = 6.  # period for wma calculation; 0 if no smoothing
    #s = 2.  # sigma for wma calculation

    #thaw_threshold = 3 # set threshold for number of days above freezing required to allow runoff
    thaw_threshold = round(thaw_threshold)

    #freeze_threshold = 2 # set threshold for number of days above freezing required to stop runoff
    freeze_threshold = round(freeze_threshold)

    glacier_2H = min(met['d2HP'])  # glacier isotopes default to minimum monthly precip values from met-input
    glacier_18O = min(met['d18OP'])

    # The R/P ratio is assigned based on air temperature
    #rp_ratio_freeze = 0.2 # When temps are freezing or below
    #rp_ratio_cold = 0.4 # Cold but above freezing (0°C < T <= 10°C)
    #rp_ratio_mild = 0.5 # Mild temperatures (10°C < T <= 20°C)
    #rp_ratio_warm = 0.1 # Warm temperatures (T > 20°C)

    # Temperature thresholds can be edited in the function a few blocks below, if desired #

    # Additional met file parameters to scale
    #met['WIND'] = met['WIND'] * wind_scale  # Scale down wind speed in the meterological input file

    # =============================================================================
    # =========================== Calculate runoff ================================
    # =============================================================================

    # Set up variables #
    days_above_freezing = 0
    days_below_freezing = 0
    thaw_threshold_reached = False
    freeze_threshold_reached = False
    runoff_allowed = False

    SMALL_VALUE_THRESHOLD = 1e-6  # Prevent rounding errors with small amounts

    # Optional #
    #filtered_runoff_total = 0.0  # To track total filtered runoff
    #filtered_acc_total = 0.0 # To track total filtered accumulation

    #### Start main runoff loop ###
    # For each iteration:
    for i in range(n_rows):
        # Initialize accumulation and isotope values for the first timestep
        if i == 0:
            M_acc[0] = 0
            M_acc_d2H[0] = M_d2H[0]
            M_acc_d18O[0] = M_d18O[0]

        ### Part 1: Get R/P Ratio For This Timestep ###
        rp_ratio = rp_ratios[i]

        ### Part 2: Does the Temperature History Allow for Runoff? ###
        if M_T2M[i] <= 273:             # Below freezing
            days_below_freezing += 1
            days_above_freezing = 0
        else:                           # Above freezing
            days_below_freezing = 0
            days_above_freezing += 1

        # Fall threshold
        if days_below_freezing >= freeze_threshold and not freeze_threshold_reached:
            runoff_allowed = False # No runoff
            freeze_threshold_reached = True # Set fall flag
            thaw_threshold_reached = False # Reset spring flag
            #print(f"Fall threshold reached on day {i}, runoff stopped.") # for debugging

        # Spring threshold
        if days_above_freezing >= thaw_threshold and not thaw_threshold_reached:
            runoff_allowed = True # Allow runoff
            thaw_threshold_reached = True # Set spring flag
            freeze_threshold_reached = False # Reset fall flag
            #print(f"Spring threshold reached on day {i}, runoff allowed.")

        ### Part 3: Calculate Runoff (if allowed) ###
        # If runoff is allowed (based on temp), calculate runoff:
        if runoff_allowed:
        ### This is the runoff calculation ###
            M_runoff[i] = (M_tp[i] * rp_ratio) + (M_acc[i - 1] * melt_ratio * rsm_ratio) + \
                    (glacier_flux) + (M_acc[i - 2] * melt_ratio * (1 - rsm_ratio))
            # precipitation contribution: 'M_tp[i] * rp_ratio'
            # previous accumulation contribution: 'M_acc[i - 1] * melt_ratio * rsm_ratio'
            # glacier flux contribution: 'glacier_flux'
            # older accumulation contribution: 'M_acc[i - 2] * melt_ratio * (1 - rsm_ratio)'

        # If runoff amount is very low:
            if M_runoff[i] < SMALL_VALUE_THRESHOLD:
                #filtered_runoff_total += M_runoff[i]

                M_runoff_d2H[i] = 'NaN' # Set runoff isotopes to NaNs
                M_runoff_d18O[i] = 'NaN'

                M_acc[i] = M_acc[i - 1] # Keep accumulation unchanged
                M_acc_d2H[i] = M_acc_d2H[i - 1] # Keep accumulation isotope values unchanged
                M_acc_d18O[i] = M_acc_d18O[i - 1]

        # If runoff is 'normal' (not too low):
            else:
                # Update accumulation
                M_acc[i] = M_acc[i - 1] * (1 - melt_ratio) # Calculate new accumulation

                # Update accumulation d2H and d18O values
                M_acc_d2H[i] = M_acc_d2H[i - 1]
                M_acc_d18O[i] = M_acc_d18O[i - 1]

                # If accumulation is very small, set to zero and isotopes to NaNs
                if M_acc[i] < SMALL_VALUE_THRESHOLD:
                #filtered_acc_total += M_acc[i]

                    M_acc[i] = 0.0
                    M_acc_d18O[i] = 'NaN'
                    M_acc_d2H[i] = 'NaN'

            # Calculate runoff d2H
                M_runoff_d2H[i] = (M_tp[i] * rp_ratio * M_d2H[i] / M_runoff[i]) + \
                            (M_acc[i - 1] * melt_ratio * rsm_ratio * M_acc_d2H[i - 1] / M_runoff[i]) + \
                            (glacier_flux * glacier_2H / M_runoff[i]) + \
                            (M_acc[i - 2] * melt_ratio * (1 - rsm_ratio) * M_acc_d2H[i - 2] / M_runoff[i])
                            # Precip contribution
                            # Previous accumulation contribution
                            # Glacier flux contribution
                            # Older accumulation contribution

                # Calculate runoff d18O (same way as d2H)
                M_runoff_d18O[i] = (M_tp[i] * rp_ratio * M_d18O[i] / M_runoff[i]) + \
                            (M_acc[i - 1] * melt_ratio * rsm_ratio * M_acc_d18O[i - 1] / M_runoff[i]) + \
                            (glacier_flux * glacier_18O / M_runoff[i]) + \
                            (M_acc[i - 2] * melt_ratio * (1 - rsm_ratio) * M_acc_d18O[i - 2] / M_runoff[i])

                #print(f"Day {i}: Updated Accumulated Isotopes: d2H={M_acc_d2H[i]}, d18O={M_acc_d18O[i]}")

        ### Part 4: Handle Cases With No Runoff ###
        # If NO temperature conditions are met to have runoff (runoff is not allowed):
        else:
            M_runoff[i] = 0  # No runoff (set runoff amount to 0 mm)
            M_runoff_d2H[i] = 'NaN' # Isotope values are set to NaN
            M_runoff_d18O[i] = 'NaN'

            if M_T2M[i] <= 273:
                M_acc[i] = M_acc[i - 1] + M_tp[i]  # Accumulation updated by adding current precipitation
            else:
                M_acc[i] = M_acc[i - 1] # If it's above freezing, carry over accumulation

            # Accumulation isotopes
            # If previous accumulation and current precip are 0:
            if M_acc[i - 1] == 0 and M_tp[i] == 0:
                M_acc_d2H[i] = 'NaN' # Set isotope values to NA
                M_acc_d18O[i] = 'NaN'

            # If previous accumulation is 0 but there's precip:
            elif M_acc[i - 1] == 0 and M_tp[i] > 0:
                M_acc_d2H[i] = M_d2H[i]  # Isotope values match current precip
                M_acc_d18O[i] = M_d18O[i]

            # If neither of the above are met, update isotope values as a weighted average to previous accumulation
            # and current precip
            else:
                M_acc_d2H[i] = ((M_acc[i - 1] * M_acc_d2H[i - 1]) / (M_acc[i - 1] + M_tp[i])) + \
                        ((M_tp[i] * M_d2H[i]) / (M_acc[i - 1] + M_tp[i]))
                M_acc_d18O[i] = ((M_acc[i - 1] * M_acc_d18O[i - 1]) / (M_acc[i - 1] + M_tp[i])) + \
                            ((M_tp[i] * M_d18O[i]) / (M_acc[i - 1] + M_tp[i]))

        ### Part 5: Replace NaN Runoff Isotopes With Precip Isotopes ###
        # For any runoff isotope values that are NA/inf/-inf, replace with monthly precip isotope values from the met-input file
        if not np.isfinite(M_runoff_d18O[i]):
            M_runoff_d18O[i] = M_d18O[i]

        if not np.isfinite(M_runoff_d2H[i]):
            M_runoff_d2H[i] = M_d2H[i]
            #print(f"Replacing NaN d2H on day {i} Runoff d18O={M_runoff_d2H[i]}")

        #print(f"Day {i}: Temp={M_T2M[i]}, Precip={M_tp[i]}, Runoff={M_runoff[i]}, Accum={M_acc[i]}, Stored Accum={M_acc[i - 1]}, Accum Isotopes: d2H={M_acc_d2H[i]}, d18O={M_acc_d18O[i]}")

    #print(f"Total filtered runoff: {filtered_runoff_total} mm")
    #print(f"Total filtered accumulation: {filtered_acc_total} mm")

    # =============================================================================
    # =========================== Smooth runoff ===================================
    # =============================================================================

    # Smooth runoff across timesteps using a weighted moving average (wma) with a
    # Gaussian tail

    # Define the function called gtail_wma
    def gtail_wma(arr, period, sigma):
        # Period = number of data points the moving average is calcluated over
        period = ceil(period / 2.) * 2 # If period is odd, round up so it's even
        # Range of indices around 0 -- this is the span of the Gaussian kernel, used
        # to calc the weighted average
        r = range(-int(period / 2), int(period / 2) + 1)
        # Generate the Gaussian (normal distribution) kernel
        kernel = np.asarray([1 / (sigma * sqrt(2 * pi)) * exp(-float(x) ** 2 / (2 * sigma ** 2)) for x in r])
        # The right half of the Gaussian/normal distribution is set to 0, giving weight
        # to previous values but not future ones
        kernel[range(int(period / 2 + 1), int(period + 1))] = 0
        # Normalize and flip (reverse) the kernel
        knorm = np.flip(kernel / kernel.sum())
        # 'np.convolve' applies the kernel to the input array we give the function,
        # creating a smoothed version of the array (our data) & 'same' makes sure
        # the output array is the same length as the input array
        return np.convolve(arr, knorm, 'same')

    ## This line applies the smoothing function to our calculated runoff data,
    # called M_runoff
    M_runoff_wma = gtail_wma(M_runoff, period=p, sigma=s)

    ## Also smooth the runoff d2H and d18O using the function
    # Note: Sometimes runoff amount is 0, resulting in divide by zero and NAs. Ignore
    # warnings for divide by zero and calculate smoothed d2H and d18O values
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)

        M_runoff_d2H_wma = gtail_wma(M_runoff * M_runoff_d2H, period=p, sigma=s) / M_runoff_wma
        M_runoff_d18O_wma = gtail_wma(M_runoff * M_runoff_d18O, period=p, sigma=s) / M_runoff_wma

    # Replace any non-finite values (NaN, inf, -inf) with original, unsmoothed data
    M_runoff_d2H_wma[~np.isfinite(M_runoff_d2H_wma)] = M_runoff_d2H[~np.isfinite(M_runoff_d2H_wma)]
    M_runoff_d18O_wma[~np.isfinite(M_runoff_d18O_wma)] = M_runoff_d18O[~np.isfinite(M_runoff_d18O_wma)]

    # # =============================================================================
    # # =========================== Output Files ====================================
    # # =============================================================================

    # # Format and export met-input file +===========================================
    met.drop(columns=['d2HP', 'd18OP'], inplace=True) # Drop the precip isotope columns temporarily

    # Format the runoff variables into our completed meterological input file in the correct order 
    met['RUNOFF'] = M_runoff_wma # Runoff amount (mm)
    met['d18OP'] = M_d18O # Precipitation d18O (per mil)
    met['d18OR'] = M_runoff_d18O_wma # Runoff d18O (per mil)
    met['d2HP'] = M_d2H # Precipitation d18O (per mil)
    met['d2HR'] = M_runoff_d2H_wma # Runoff d2H (per mil)

    # Other values within runoff calculation that could be compared with observations
    met['ACC'] = M_acc
    met['d18OACC'] = M_acc_d18O
    met['d2HACC'] = M_acc_d2H

    return met