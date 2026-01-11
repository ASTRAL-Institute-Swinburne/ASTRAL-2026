# Week 1 Docs
## Installed Python

The first task for all students was to install Python and install the necessary libraries as well.

To install Python, go to [https://www.python.org/](https://www.python.org/) and install the **standalone installer**.

Then install the necessary libraries `matplotlib`, `numpy`, `scipy`, `pandas` using the `pip` command - 

```bash

pip install <library_name>

```

If this does not work, an alternative is - 

```bash

python -m pip install <library_name>

```

If using Mac or Linux, please use `python3` instead of `python` in those commands.

## Gaia Data

We then downloaded data from the Gaia Telescope and began analysing this data.

To access the data, click the link [here](https://github.com/ASTRAL-Institute-Swinburne/ASTRAL-2026/tree/main/gaia).

For Gaia Documentation, please visit the ASTRAL Wiki page [here](https://github.com/ASTRAL-Institute-Swinburne/ASTRAL-2026/wiki/Gaia).

### Basics of Gaia Analysis

#### RA and DEC Plot

We first plotted the Right Ascension (RA) vs. the Declination (DEC) from the Gaia Data.

To do this, please use the sample code below - 

```Python

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

filepath = 'path/to/your/file.csv'
data = pd.read_csv(filepath)
data_cleaned = data.dropna(subset=['provide column name here'])

# Create figure and set font size to 12
plt.rcParams.update({'font.size': 12})
plt.figure(figsize=(12,8)) # Set figure size ratio to 12:8

# Optional: add plt.subplot(number_rows, number_columns, cell_number) to create multiple subplots.
# NOTE! If you do create subplots, lines 16 onwards need to be copied and changed for all subplots.

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
#### Colour Magnitude Diagram

We then plotted the colour magnitude diagram (CMD Diagram), also called the Hertzsprung-Russell Diagram (HR Diagram).

To do this, we need to plot colour on the x-axis and absolute magnitude on the y-axis.

To do this, we need a couple of things - 

- `BP-RP` - this is the colour of the star
- `parallax` - this can be used to calculate the distance to the star. Units are milliarcseconds
- `phot_g_mean_mag` - this is the apparent magnitude of the star, which can be used to calculate the absolute magnitude.

To calculate the absolute magnitude, use the formula below - 

$$
M_G = m_G - 5log_{10}(distance) + 5
$$

And to calculate the distance, you can use the following formula - 

$$
distance = \frac{1000}{parallax}
$$

#### X, Y and Z coordinates

Next, we plotted the X, Y and Z coordinates of the stars on a 3D plot.

To do this, we need a couple of things - 

- `l` - The galactic longitude of the star
- `b` - The galactic latitude of the star
- `distance` - the distance to the star

Use the formulas below to calculate the X,Y and Z coordinates - 

$$
X = distance * \cos(b) \times cos(l)
$$
$$
Y = distance * \cos(b) \times sin(l)
$$
$$
Z = distance * \sin(b)
$$
