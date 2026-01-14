import matplotlib.pyplot as plt
import sys
import math as m
import numpy as np
import galpy.util.plot as plot
import galpy.potential as potential
from galpy.potential import MWPotential2014
from galpy.orbit import Orbit

def initial_pars():
    # get command line arguments
    nargs = len(sys.argv) - 1
    if (nargs<=6):
        print("Specify coordinate system, X, Y, Z, U, V, W in kpc and km/s")
        print("e.g. python oneorb.py cart 8 0 0 10 225 10")
        print("OR")
        print("Coordinate system, R, vR, vT, z, vz, phi")
        print("distances in kpc, velocities in km/s, angles in degrees")
        print("python oneorb.py cyl 8.0 10.0 225.0 0.0 10.0 0.0")
        print()
        print('Coordinate system must be "cyl" or "cart"')
        sys.exit()
    if (nargs==7):
        type = sys.argv[1]
        print("Coordinate system (Cartesian or cylindrical) : ",type)
        if type == "cyl":
            R = float(sys.argv[2])
            vR = float(sys.argv[3])
            vT = float(sys.argv[4])
            z = float(sys.argv[5])
            vz = float(sys.argv[6])
            phi = float(sys.argv[7])
            phi = phi / (180.0/np.pi)
        elif type == "cart":
            x = float(sys.argv[2])
            y = float(sys.argv[3])
            z = float(sys.argv[4])
            U = float(sys.argv[5])
            V = float(sys.argv[6])
            vz = float(sys.argv[7])
            R = np.sqrt(x**2+y**2)
            phi = m.atan2(y,x)
            vR = U*np.cos(phi)-V*np.sin(phi)
            vT = U*np.sin(phi)+V*np.cos(phi)
            print("R, vR = ",R, vR," kpc, km/s")
            print("vT    = ",vT," km/s")
            print("z, vz = ",z, vz," kpc, km/s")
            print("phi   = ",phi*180.0/np.pi," deg")
    else:
        if type == "cyl":
            print("Needs system, R, vR, vT, z, vz, phi")
            print("distances in kpc, velocities in km/s, angles in degrees")
            print("python oneorb.py cyl 8.0 160.0 370.0 0.0 110.0 0.0")
            sys.exit()
        elif type == "cart":
            print("Needs system, X, Y, Z, U, V, W")
            print("distances in kpc, velocities in km/s")
            print("python oneorb.py cart 8 0 0 0 220 0")
            sys.exit()

    Rsun = 8.0
    Vsun = 220.0
    return R/Rsun,vR/Vsun,vT/Vsun,z/Rsun,vz/Vsun,phi


####################################################
# get the initial parameters of the star.
# cylindrical or cartesian coords must be
# specified as first parameter on the command line

vxvv0 = initial_pars()

# Rsun, V_LST
ro = 8.0
vo = 220.0

from galpy.util import conversion

print("time conversion = ",conversion.time_in_Gyr(vo,ro), " Gyr")
time_conversion = conversion.time_in_Gyr(220.,8.)

# define an orbit object
o = Orbit(vxvv=vxvv0, ro=ro, vo=vo)

# set up the time array
# Npts are times at which to return the orbit
Npts = 1000
ts = np.linspace(0.0,10.0/time_conversion,Npts)

#integrate the orbit over ts (time) 
o.integrate(ts, MWPotential2014)

plt.figure(figsize=(10,10))

plt.subplot(131)
plt.plot(ts*time_conversion, np.array(o.R(ts)))
plt.xlabel("time [Gyr]")
plt.ylabel("R [kpc]")

plt.subplot(132)
plt.plot(ts*time_conversion, np.array(o.z(ts)))
plt.xlabel("time [Gyr]")
plt.ylabel("Z [kpc]")

plt.subplot(133)
plt.plot(o.x(ts), o.y(ts))
plt.xlabel("X [kpc]")
plt.ylabel("Y [kpc]")

plt.show()

