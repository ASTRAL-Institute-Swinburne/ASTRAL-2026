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
