import os
import argparse
import numpy as np
from PIL import Image
import pandas as pd
from starmap_fns import Teff_to_RGB, BPRP_to_teff, lb_to_xy
from scipy.ndimage import gaussian_filter
from concurrent.futures import ThreadPoolExecutor
import time

PERCENTAGE = 0.10
DEFAULT_GAUSSIAN_SIGMA = 1.0
HEIGHT = 1080*2
WIDTH = 6400 
DEFAULT_CSV_PATH = "../data/47Tuc_filtered.csv"
DEFAULT_OUT_PATH = "../starmap/results/output.png"

# arguments
parser = argparse.ArgumentParser(description="Render a star map image from a Gaia-style CSV.")
parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the input CSV file")
parser.add_argument("--out", default=DEFAULT_OUT_PATH, help="Path to the output image file")
parser.add_argument("--gaussian", default=1.0, help="Gaussian blur in pixels")
parser.add_argument("--percentage", default=1.0, help="Percentage of max to set to 255")
parser.add_argument("--lmin", default=-180,help="l minimum")
parser.add_argument("--lmax", default=180,help="l maximum")
parser.add_argument("--bmin", default=-90,help="b minimum")
parser.add_argument("--bmax", default=90,help="b maximum")

args = parser.parse_args()

csv_path = args.csv
out_path = args.out
gaussian = float(args.gaussian)
percentage = float(args.percentage)
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# read data
df = pd.read_csv(csv_path)
df = df.dropna(subset=["phot_g_mean_mag", "bp_rp", "l", "b"])
print(f"Read {len(df)} stars")

l = df["l"].to_numpy()
# convert to be between +/- 180
l = np.where( l>180, l - 360, l)
b = df["b"].to_numpy()
bprp = df["bp_rp"].to_numpy()
mag = df["phot_g_mean_mag"].to_numpy()

l_min, l_max = l.min(), l.max()
b_min, b_max = b.min(), b.max()
print("lmin", l_min, "lmax", l_max, "bmin", b_min, "bmax", b_max)

print("lmin lmax bmin bmax",args.lmin,args.lmax,args.bmin,args.bmax)

l_min = float(args.lmin)
l_max = float(args.lmax)
b_min = float(args.bmin)
b_max = float(args.bmax)

star_brightness = 10 ** (-0.4 * mag)
print(f"brightness range: {star_brightness.min()} to {star_brightness.max()}")

start_color = time.time()

pixel_x, pixel_y = np.vectorize(lb_to_xy, otypes=[int, int])(l, b, HEIGHT, WIDTH, l_min, l_max, b_min, b_max)
# I think this has unintended consequences so is commented out
# pixel_x = np.clip(pixel_x, 0, HEIGHT - 1)
# pixel_y = np.clip(pixel_y, 0, WIDTH - 1)

def clip_teff(bp_rp):
    teff = BPRP_to_teff(bp_rp)
    return np.clip(teff, 2000, 40000)

star_teff = np.array([clip_teff(bp) for bp in bprp], dtype=np.float32)

def compute_rgb(teff):
    return np.array(Teff_to_RGB(teff), dtype=np.float32)

# multithreaded RGB computation
with ThreadPoolExecutor() as executor:
    star_rgb = np.stack(list(executor.map(compute_rgb, star_teff)), axis=0)

star_rgb *= star_brightness[:, None]

print(f"RGB Conversion took {time.time() - start_color:.2f} seconds")

start_accumulation = time.time()
img_array = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
print("Accumulating star data...")
# confusing convention for images in pillow
mask = (pixel_x >= 0) & (pixel_x < HEIGHT) & (pixel_y >= 0) & (pixel_y< WIDTH)
for i in range(3):
    np.add.at(img_array[:, :, i], (pixel_x[mask], pixel_y[mask]), star_rgb[:, i][mask])

print(f"Accumulation took {time.time() - start_accumulation:.2f} seconds")

start_blur = time.time()
print("Enacting blur...")
def blur_channel(channel_index):
    return gaussian_filter(img_array[:, :, channel_index], sigma=gaussian)

with ThreadPoolExecutor() as executor:
    blurred_channels = list(executor.map(blur_channel, range(3)))

blurred = np.stack(blurred_channels, axis=2)

print(f"Blurring took {time.time() - start_blur:.2f} seconds")

max_color = blurred.max()
print("max_color:", max_color)
if max_color > 0:
    blurred /= (max_color * percentage / 100.0)
    blurred *= 255

# rescale any pixel > 255 in any channel
max_rgb_per_pixel = blurred.max(axis=2)
mask = max_rgb_per_pixel > 255
for i in range(3):
    blurred[:, :, i][mask] = blurred[:, :, i][mask] / max_rgb_per_pixel[mask] * 255

result_image = np.clip(blurred, 0, 255).astype(np.uint8)

# where is the maximum pixel?
# say where the max R,G, or B is and its value

# Flatten and find global max
global_max_value = np.max(result_image)
global_max_index = np.argmax(result_image)

# Convert flat index to 3D coordinates
i, j, k = np.unravel_index(global_max_index, result_image.shape)
print("highest value is at ",i,j,k," with values R: ",result_image[i,j,0]," G: ", result_image[i,j,1]," B: ",result_image[i,j,2])
 
Image.fromarray(result_image, "RGB").save(out_path)
print(f"Saved to {out_path}")
