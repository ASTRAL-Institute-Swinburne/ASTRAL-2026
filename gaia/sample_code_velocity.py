from velocity_calculator import calculate_space_velocity

ra = (1 + 9./60. + 42.3/3600.0)*15.  # deg
dec = 61 + 32./60.0 + 49.5/3600.0    # deg
pmra = 627.89  # mas/yr
pmdec = 77.84  # mas/yr
dis = 144      # pc
vrad = -321.4  # km/s

u, v, w = calculate_space_velocity(distance=dis, lsr=True, ra=ra, dec=dec, pmra=pmra, pmdec=pmdec, vrad=vrad) #, plx=None):

print("Test example is Hipparcos star HD6755")

print('U, V, W')
print(u, v, w)

# Exercise : Use Gaia data for a star of your choice!