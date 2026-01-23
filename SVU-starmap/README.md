# SVU Starmap creation

This documentation provides instructions on producing a map of stars. The program matthew_map.py will plot any stars provided from a csv file on a black image, creating an image of the stars in space. The following functions documented are all found within mathew_map.py, contributing to making the image.   

The overall steps for the process of image creation are:    
1. downloading matthew_map.py and starmap_fns.py 
2. generating a CSV from the GAIA database
3. removing points outside the globular cluster using one of the filtering algorithms
4. running matthew_map.py with the filtered csv to produce an image

## Generating CSV Files for Globular Clusters

#### What it does
This step uses a line of code in the terminal to generate CSV files for certain globular clusters, retrieved from a code that pulls data from a database with 1.811 billion stars. The data in these files can then be plotted into an image.

#### How to Use it
1. From GitHub, a file under gaia is named gaia_analyse.py, after downloading this code, upload it onto your Visual Studio Code directory.     
2. Open up a terminal in VS Code and insert the following code
'''   
python gaia_analyse.py --host 192.168.100.220 diagnose "cone_source name of globular cluster x" --output-dir name of globular cluster
'''
3. Where it says ‘name of globular cluster’ replace it with the name of your chosen globular cluster. The ‘x’ represents the radius in degrees around the globular cluster, this can be changed based on your requirements.    
4. After writing the required information, press enter and the code should run and generate a subfile in your VS Code directory named after the Globular Cluster. In that subfile there will be different graphs highlighting key information of the Globular CLuster. There will also be a CSV file named shortlist.csv, rename it to the name of the Globular Cluster.csv.      
This same code can be used in the terminal for different Globular Clusters over and over again.     

#### Key Mistakes

Make sure the gaia_analyse.py is saved within the directory uploaded on your VS Code.     
If the gaia_analyse.py is under a subfile make sure that your terminal recognises where you're retrieving the information from, this can be done by typing ‘cd change name of subfile’. Now the terminal will retrieve the code from the correct file path.     
Make sure you're connected to the Fourier Space wifi, the database from which the stars are retrieved from is connected to that WiFI, the code will not run unless your device is connected to Fourier Space.     

#### Example (Assuming the gaia_analyse.py is in the correct place)     

Computing Globular Cluster NGC1261 with a 1 degree radius. 

```
PS C:\Users\muhda\Desktop\fatimahswin> python gaia_analyse.py --host 192.168.100.220 diagnose "cone_source NGC1261 1" --output-dir NGC1261
```

## Matthew_map.py

#### What it does

This program plots stars from a csv file on a black screen and saves it as a png file within the directory the script is run from. This program calculates the distance, brightness, and colour of the stars. The brighter stars should appear more vibrant, while the dim stars will be darker and less clear. All stars appear slightly blurry, to make their appearance more realistic. In addition, the stars are coloured to appear the same as their actual colours. The generated image should appear the same as if one was actually looking at the stars through a telescope.

#### How to Use it

1. Download the file and download starmap_fns.py into the same folder as matthew_map.py
3. Change the df = read_csv("../gaia/47Tuc/shortlist.csv") to df = read_csv(“##YOUR CSV PATH##”)    
4. Change the percentage, height and width to the desired values    
5. Open the image (Which will be saved to the directory it was run from)   

## starmap_fns.py Functions

This is a library of functions used within the matthew_map.py script. To use these functions in a script, the script must be in the same folder as the starmap_fns.py file and the functions must be imported using this line of code:

```
from starmap_fns import *
```
The functions can then be called within the script.

### Teff To RGB

#### What it does

This function takes in the Temperature (T effective/Teff) value of a star and converts it to an RGB values, which is the approximate colour of the star.

#### How to use it

The function takes in 1 argument – A Teff Value (Float) in Kelvin (Which can be found using BPRP to Teff)    
This function returns 1 output – An array of floats of length 3 where the first element is the red value, the second is the green value and the third is the blue between 0-255 inclusive.

#### Example (Assuming the function is in the file) 

Computing the RGB colours of a star with a Teff of 1000 Kelvin

```
Teff_value = 1000.0   
Rgb = Teff_to_RGB(Teff_value)    
print(Rgb) # Output – [255.0,67.92041906,0.0] ([Red,Green,Blue])   
```
If the function is not in the file    
1. Import the file where the function is E.g import starmap_fns   
2. Instead of doing Rgb = Teff_to_RGB(Teff_value) instead do – Rgb = fileName.Teff_to_RGB(Teff_value) E.g Rgb = starmap_fns.Teff_to_RGB(Teff_value)   


### BPRP to Teff

#### What it does

This function calculates the temperature of a star, measured in kelvin, based on its colour. The colour of the star is found under the column named ‘bp_rp’ within the csv file, which defines how red or blue the star is. Cold stars are red, while the hottest stars are blue. 

#### How to use it

The function uses one argument (Float) - bprp (how red/blue the star is)    
And returns one output - Teff (contains the temperature of the star, measured in kelvins)    

The function can be used like this:    
````
from starmap_fns import BPRP_to_teff    

temp = BPRP_to_teff(df.iloc[i]['bp_rp'])      
````
In this example, temp now contains the value of teff, meaning temp is now set to the temperature of the star.    

### lb_to_xy

#### What it does

This function calculates the x & y coordinates within an array of a point in the sky, given the point’s position in galactic coordinates (L & B) and the size of the array. It returns a tuple of two integers that identifies one position within the array, allowing the point to be assigned to a pixel within an image of that size. This is intended to be used while iterating over a dataframe where L & B are columns in order to generate an image.

#### How to use it

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

#### Example usage

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

## Contributors

#### Mentors
Professor Matthew Bailes    
Daniel Rosina    
Lucy O'Shea    
Rebecca Koehne    

#### Cohort
Eve Cumming    
Fatimah Adnan    
Jana Azzam    
Prabhjeevan Singh    
Shruthi Sunnoju    
