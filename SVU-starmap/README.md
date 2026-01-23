# SVU Starmap creation

## Matthew_map.py

#### What it does:

This program plots stars from a csv file on a black screen and is saved as a png file within the same file as Mathew_map.py . This program calculates the distance, brightness, and colour of the stars. The brighter stars should appear more vibrant, while the dim stars will be darker and less clear. All stars appear slightly blurry, to make their appearance more realistic. In addition, the stars are coloured to appear the same as their actual colours. The generated image should appear the same as if one was actually looking at the stars through a telescope.

#### How to Use it:

1. Download the file and download starmap_fns.py into the same folder as matthew_map.py    
2. Change the df = read_csv("../gaia/47Tuc/shortlist.csv") to df = read_csv(“##YOUR CSV PATH##”)    
3. Change the percentage, height and width to the desired values    
4. Open the image (Which will be saved to the directory it was run from)   



## starmap_fns.py Functions

This is a library of functions used within the matthew_map.py script.

### Teff To RGB:

#### What it does:

This function takes in the Temperature (T effective/Teff) value of a star and converts it to an RGB values, which is the approximate colour of the star.

#### How to use it:

The function takes in 1 argument – A Teff Value (Float) in Kelvin (Which can be found using BPRP to Teff)    
This function returns 1 output – An array of floats of length 3 where the first element is the red value, the second is the green value and the third is the blue between 0-255 inclusive.

#### Example (Assuming the function is in the file) Computing the RGB colours of a star with a Teff of 1000 Kelvin:

```
Teff_value = 1000.0   
Rgb = Teff_to_RGB(Teff_value)    
print(Rgb) # Output – [255.0,67.92041906,0.0] ([Red,Green,Blue])   
```
If the function is not in the file    
Import the file where the function is E.g import starmap_fns   
Instead of doing Rgb = Teff_to_RGB(Teff_value) instead do –   
Rgb = fileName.Teff_to_RGB(Teff_value) E.g Rgb = starmap_fns.Teff_to_RGB(Teff_value)   


### BPRP to Teff

#### What it does:

This function calculates the temperature of a star, measured in kelvin, based on its colour. The colour of the star is found under the column named ‘bp_rp’ within the csv file, which defines how red or blue the star is. Cold stars are red, while the hottest stars are blue. 

#### How to use:

The function uses one argument (Float) - bprp (how red/blue the star is)    
And returns one output - Teff (contains the temperature of the star, measured in kelvins)    

The function can be used like this:    
````
#start of code    
from starmap_fns import BPRP_to_teff    

temp = BPRP_to_teff(df.iloc[i]['bp_rp'])    
#end of code    
````
In this example, temp now contains the value of teff, meaning temp is now set to the temperature of the star.    

### lb_to_xy

#### What is does:

This function calculates the x & y coordinates within an array of a point in the sky, given the point’s position in galactic coordinates (L & B) and the size of the array. It returns a tuple of two integers that identifies one position within the array, allowing the point to be assigned to a pixel within an image of that size. This is intended to be used while iterating over a dataframe where L & B are columns in order to generate an image.

#### How to use it:

The function takes eight arguments:    
 - L (float): the point’s galactic longitudinal coordinate   
 - B (float): the point’s galactic latitudinal coordinate    
 - Height (int): the height of the array in which the point will be plotted    
 - Width (int): the width of the array which the point will be plotted    
 - Lmax (float): the maximum longitudinal value of all points being plotted    
 - Bmax (float): the maximum latitudinal value of all points being plotted    
 - Lmin (float): the minimum longitudinal value of all points being plotted    
 - Bmin (float): the minimum latitudinal value of all points being plotted    

The function can be called like this: lb_to_xy(L, B, height, width, Lmax, Lmin, Bmax, Bmin)    
This will return a tuple of this form: (x_coordinate, y_coordinate)    
These coordinates can then be used to place the point in an array before converting the array into an image of the specified height and width.

#### Example usage:

````
# importing the function
from starmap_fns import lb_to_xy

# reading in star data as a dataframe
df = pd.read_csv(“star_data”)

# defining the limits of the L & B coordinates
lmin = df['l'].min()
lmax = df['l'].max()
bmin = df['b'].min()
bmax = df['b'].max()

# assigning each star to a cell in the array
for i in range(len(df)):
	brightness = df.iloc[i][“brightness”]
	x,y = lb_to_xy(df.iloc[i]['l'],df.iloc[i]['b'],1080,1920,lmin,lmax,bmin,bmax)
	img_array[x,y] = brightness

# converting array into an RGB image
img = img.fromarray(img_array, ‘RGB’)
```` 
