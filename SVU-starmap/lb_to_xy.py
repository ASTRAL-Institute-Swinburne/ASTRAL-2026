import numpy as np


def lb_to_xy(l, b, height, width, lmin, lmax, bmin, bmax):
    #height, width = 1080, 1920
   
    lrange = lmax-lmin
    brange = bmax-bmin
    lfactor = width/lrange
    bfactor = height/brange
       
    return (int(bfactor*(b-bmin)), int(lfactor*(l)))




# test
print(lb_to_xy(47, -24, 1080, 1920, 0, 360, -90, 90))
(396, 250)
