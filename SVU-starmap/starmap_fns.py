import numpy as np


def lb_to_xy(l, b, height, width, lmin, lmax, bmin, bmax):
    #height, width = 1080, 1920
   
    lrange = lmax-lmin
    brange = bmax-bmin
    lfactor = width/lrange
    bfactor = height/brange
       
    return (int(bfactor*(b-bmin)), int(lfactor*(l)))

def BPRP_to_teff(bprp):
    """returns in kelvins"""
    teff = 5040/(0.4929+0.5092*bprp-0.0353*bprp**2)
    # print("teff:",teff)
    return teff

def Teff_to_RGB(colourTemperature: float) -> np.ndarray:
    colourTemperature = np.clip(colourTemperature, 1000, 40000)
    tmp = colourTemperature / 100.0


    # Red
    if tmp <= 66:
        red = 255
    else:
        red = 329.698727446*(tmp - 60)**-0.1332047592
   
    # Green
    if tmp <= 66:
        green = 99.4708025861*np.log(tmp) - 161.1195681661
    else:
        green = 288.12211695283*(tmp-60)**-0.0755148492
   
    # Blue
    if tmp >= 66:
        blue = 255
    elif tmp <= 19:
        blue = 0
    else:
        blue = 138.5177312231 * np.log(tmp - 10) - 305.0447927307


    return np.clip((red,green,blue),0,255)
