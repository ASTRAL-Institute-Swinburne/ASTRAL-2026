# Gaia DR3 Data Documentation

Gaia is a European Space Agency (ESA) space telescope that measures the **positions, distances, and motions of stars** in our galaxy.

## Accessing data
Download the CSV files within this folder to access Gaia Data.

- `bright.csv` is a Gaia dataset of the brightest stars by apparent magnitude (how bright they are when we view them from Earth).
- `gaia-askap-matches.csv` - stars that have been found using the ASKAP telescope (radio stars) and have been matched to Gaia stars.
- `gaia-2.csv` and `gaia-3.csv` - more stellar data from Gaia.

## 1. Identifying a Star

| Column      | What it means                                                           |
| ----------- | ----------------------------------------------------------------------- |
| `source_id` | A unique ID number for each star (like a barcode)                       |
| `ref_epoch` | The year when the position measurements are referenced (usually 2016.0) |

## 2. Position of the Star in the Sky

These columns tell us **where the star is located** on the sky.

| Column      | Units   | Explanation                                     |
| ----------- | ------- | ----------------------------------------------- |
| `ra`        | degrees | Right Ascension – similar to longitude on Earth |
| `dec`       | degrees | Declination – similar to latitude on Earth      |
| `ra_error`  | mas     | Uncertainty in Right Ascension                  |
| `dec_error` | mas     | Uncertainty in Declination                      |

*(mas = milliarcseconds, 1/3600000 of a degree)*

## 3. Distance to the Star (Parallax)

Gaia measures distance using **parallax**, which is the apparent shift of a star due to Earth’s motion around the Sun.

| Column           | Units | Explanation             |
| ---------------- | ----- | ----------------------- |
| `parallax`       | mas   | Measured parallax angle |
| `parallax_error` | mas   | Uncertainty in parallax |

**Important notes for students:**

* A **larger parallax** means the star is **closer**.
* Parallax values can sometimes be **negative** due to measurement uncertainty.

## 4. Motion of the Star (Proper Motion)

These columns describe how fast the star moves **across the sky**.

| Column        | Units  | Explanation                        |
| ------------- | ------ | ---------------------------------- |
| `pmra`        | mas/yr | Motion in Right Ascension per year |
| `pmdec`       | mas/yr | Motion in Declination per year     |
| `pmra_error`  | mas/yr | Error in RA motion                 |
| `pmdec_error` | mas/yr | Error in Dec motion                |

## 5. Brightness of the Star (Photometry)

Gaia measures brightness in three colours:

* **G** (Gaia's observing band)
* **BP** (blue light)
* **RP** (red light)

| Column             | Units | Explanation                     |
| ------------------ | ----- | ------------------------------- |
| `phot_g_mean_mag`  | mag   | Brightness in G band            |
| `phot_bp_mean_mag` | mag   | Brightness in blue light        |
| `phot_rp_mean_mag` | mag   | Brightness in red light         |
| `bp_rp`            | mag   | Colour of the star (blue − red) |

**Key idea:**

* Smaller magnitude = **brighter star**
* `bp_rp` tells us about **temperature** (blue = hotter, red = cooler)

## 7. Speed Towards or Away from Earth (If Available)

Some stars have their **radial velocity** measured.

| Column                  | Units | Explanation                      |
| ----------------------- | ----- | -------------------------------- |
| `radial_velocity`       | km/s  | Speed towards or away from Earth |
| `radial_velocity_error` | km/s  | Uncertainty in speed             |

## 8. Physical Properties of the Star (Some Stars Only)

These values are estimated using models.

| Column             | Units | Explanation                       |
| ------------------ | ----- | --------------------------------- |
| `teff_gspphot`     | K     | Surface temperature               |
| `logg_gspphot`     | dex   | Surface gravity                   |
| `mh_gspphot`       | dex   | Metal content compared to the Sun |
| `distance_gspphot` | pc    | Estimated distance                |

## 9. Is the Star Variable?

| Column               | Explanation                     |
| -------------------- | ------------------------------- |
| `phot_variable_flag` | Indicates if brightness changes |
| `best_class_name`    | Type of variable star           |

## 10. Sample code to plot parameters

Simple Python script to plot anything from a CSV file.

```Python

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

filepath = 'path/to/your/file.csv'
data = pd.read_csv(filepath)
data_cleaned = data.dropna(subset=['provide column name here'])

# Create figure and set font size to 12
plt.rcParams.update({'font.size': 12})
plt.figure(figsize=(12,8))

# Style grid
plt.grid(color='whitesmoke', linestyle='-', linewidth=1)
plt.gca().set_axisbelow(True) # Make sure it is below all the points

plt.scatter(data['RA'], data['DEC'], c='dodgerblue', s=10, label='Label here') # Plot RA vs. DEC with a dot size of 10
plt.xlabel('X Axis Label')
plt.ylabel('Y Axis Label')

# Style tickmarks on both x axis and y axis to have font size of 10
plt.xticks(fontsize=10)
plt.yticks(fontsize=10)
plt.tick_params(axis='both', which='both', direction='in') # Make it so that the tickmarks are within the figure rectangle

plt.tight_layout() # Reduce padding around figure
plt.legend() # Add a legend
plt.grid(True) # Apply the grid
plt.show() # Show the plot
plt.savefig('filename.png') # Save plot to filename.png

```
