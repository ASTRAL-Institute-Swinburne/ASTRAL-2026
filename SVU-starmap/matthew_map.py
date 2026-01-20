import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import pandas as pd
from starmap_fns import Teff_to_RGB, BPRP_to_teff, lb_to_xy

percentage = 0.1

df = pd.read_csv("../gaia/47Tuc/shortlist.csv")
print("read file")
df = df.dropna(subset=['phot_g_mean_mag', 'bp_rp'])
print("dropped Nans")
height = 2160
width = 3840

lmin = df['l'].min()
lmax = df['l'].max()
bmin = df['b'].min()
bmax = df['b'].max()
#
# lmin = 0
# lmax = 360
# bmin = -90
# bmax = 90

print("lmin ",lmin)
print("lmax ",lmax)
print("bmin ",bmin)
print("bmax ",bmax)

# Drop rows with missing values first
# df = df.dropna(subset=['phot_g_mean_mag', 'bp_rp'])

# Get RGB colors directly from BP-RP
# TO DO: write your own bprp_to_rgb function: go from bp_rp_to_teff and then from teff_to_rgb

# array for raw fluxes from the stars

img_array = np.zeros((height,width,3))

for i in range(len(df)):
    if (i%10000==0):
        print("i=",i)
    temp = BPRP_to_teff(df.iloc[i]['bp_rp'])
    RGB = Teff_to_RGB(temp)
    x,y=lb_to_xy(df.iloc[i]['l'],df.iloc[i]['b'],height,width,lmin,lmax,bmin,bmax)
    if (x>=height): 
        x = height-1
    if (y>=width): 
        y = width-1
    brightness = 10**(-0.4*df.iloc[i]['phot_g_mean_mag'])
    for j in range(len(RGB)):
        # will need to be enhanced for the sum and scaled
        # print("temp = ",temp," R=",RGB[0]," G=",RGB[1]," B=",RGB[2])
        img_array[x,y,j]+=RGB[j]*brightness

# future image array that will be blurred
blurred = img_array

#blurred = blurred.clip(0, 1000) # no longer needed
print("enacting blur")
for i in range(len(RGB)):
    blurred[:,:,i] = gaussian_filter(img_array[:,:,i], sigma=0.5)

max_color = blurred.max()
print("max_color is ",max_color)
blurred/=(max_color*percentage/100.0)
blurred*=255
min_color = blurred.min()
print("min_color after norm is ",min_color)
max_color = blurred.max()
print("max_color after norm is ",max_color)

for i in range(len(RGB)):
    print(np.max(blurred[:,:,i])," ", np.min(blurred[:,:,i]))

# transform to 8 but unsigned ints for color
# result = blurred.astype(np.uint8)
# all the brightest stars become white - need individual scaling if clipped

max_in_RGB = blurred.max(axis=2)
for i in range(width):
    for j in range(height):
        if max_in_RGB[j,i]>255:
            blurred[j,i,0]=blurred[j,i,0]/max_in_RGB[j,i]*255
            blurred[j,i,1]=blurred[j,i,1]/max_in_RGB[j,i]*255
            blurred[j,i,2]=blurred[j,i,2]/max_in_RGB[j,i]*255            

result = np.clip(blurred, 0, 255).astype(np.uint8)

# need to loop over every star and if brightness> 255 in anything rescale by color


# Calculate brightness from magnitude - use sqrt to compress dynamic range
#brightness = 10**(-0.4 * df['phot_g_mean_mag'])
#brightness = brightness / brightness.max()

img = Image.fromarray(result, 'RGB')
img.save('first_image.1.png')
print("\nSaved to first_image.1.png")
