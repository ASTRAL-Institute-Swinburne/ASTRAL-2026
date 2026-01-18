import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import pandas as pd


def bprp_to_rgb(bp_rp):
    """Map BP-RP directly to visible star colors.
    Hot blue stars have negative bp_rp, cool red stars have positive bp_rp.
    """
    bp_rp = np.clip(bp_rp, -0.5, 4.0)
    t = (bp_rp + 0.5) / 4.5  # 0 = blue/hot, 1 = red/cool

    # Hot (blue-white) -> warm (yellow) -> cool (orange-red)
    red = np.clip(255 * (0.5 + 0.5 * t), 128, 255)      # 128-255
    green = np.clip(255 * (0.7 - 0.4 * t), 75, 180)     # varies more
    blue = np.clip(255 * (1.0 - 1.2 * t), 0, 255)       # 255 -> 0

    return np.stack([red, green, blue], axis=-1)

import argparse

#argparse to get the csv file name
parser = argparse.ArgumentParser(description='Generate star temperature image from Gaia data.')
parser.add_argument('--input', type=str, default='47TUC/shortlist.csv',
                    help='Input CSV file with Gaia data')

args = parser.parse_args()

df = pd.read_csv(args.input)

# Drop rows with missing values first
df = df.dropna(subset=['phot_g_mean_mag', 'bp_rp'])

# Get RGB colors directly from BP-RP
# TO DO: write your own bprp_to_rgb function: go from bp_rp_to_teff and then from teff_to_rgb
rgb_array = bprp_to_rgb(df['bp_rp'].values)
df['rgb'] = list(rgb_array)

print("RGB ranges across all stars:")
print("Red:", rgb_array[:, 0].min(), "-", rgb_array[:, 0].max())
print("Green:", rgb_array[:, 1].min(), "-", rgb_array[:, 1].max())
print("Blue:", rgb_array[:, 2].min(), "-", rgb_array[:, 2].max())

# Calculate brightness from magnitude - use sqrt to compress dynamic range
brightness = 10**(-0.4 * df['phot_g_mean_mag'])
brightness = brightness / brightness.max()

# Scale RGB by brightness
df['scaled'] = [rgb * b for rgb, b in zip(df['rgb'], brightness)]
# Create image
l_bins = 3840  
b_bins = 2160  
#Use the scaled star values to produce an image of l_bins and b_bins resolution


'''

img_array = np.zeros((b_bins, l_bins, 3))

l_range = df['l'].max() - df['l'].min()
b_range = df['b'].max() - df['b'].min()

print("\nL and B ranges:"
      f" L: {df['l'].min()} to {df['l'].max()} ({l_range}),"
      f" B: {df['b'].min()} to {df['b'].max()} ({b_range})")

l_idx = np.clip(((df['l'] / l_range) * l_bins).astype(int), 0, l_bins - 1)
b_idx = np.clip(((df['b'] + 90) / b_range * b_bins).astype(int), 0, b_bins - 1)

for i in range(len(df)):
    img_array[b_idx.iloc[i], l_idx.iloc[i]] += df['scaled'].iloc[i]

'''
blurred = gaussian_filter(img_array, sigma=1.5)

# Use asinh stretch to preserve colors while boosting faint stars
# This is what astronomers use for imaging
# def asinh_stretch(img, scale=0.1):
#     """Apply asinh stretch - preserves color ratios"""
#     return np.arcsinh(img * scale) / np.arcsinh(scale)

# # Normalize by luminance to preserve color ratios
# luminance = 0.2126 * blurred[:,:,0] + 0.7152 * blurred[:,:,1] + 0.0722 * blurred[:,:,2]
# lum_max = np.percentile(luminance, 99.9)  # Avoid outliers

# # Apply asinh stretch to luminance
# stretched_lum = asinh_stretch(luminance / lum_max, scale=0.5)

# # Scale original colors by stretched luminance
# result = np.zeros_like(blurred)
# with np.errstate(divide='ignore', invalid='ignore'):
#     for i in range(3):
#         result[:,:,i] = np.where(luminance > 0, 
#                                   blurred[:,:,i] / luminance * stretched_lum * 255,
#                                   0)

result = np.clip(blurred, 0, 255).astype(np.uint8)

print("\nFinal image channel ranges:")
for i, color in enumerate(['Red', 'Green', 'Blue']):
    print(f"{color}: {result[:, :, i].min()} - {result[:, :, i].max()}")

img = Image.fromarray(result, 'RGB')
img.save('star_temperature_image.png')
print("\nSaved to star_temperature_image.png")