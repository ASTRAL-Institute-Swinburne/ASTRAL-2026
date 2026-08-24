# Calculating Sun-Pulsar Separation Angles with Astropy

## Why This Matters

Observations of pulsars near the Sun are affected by increased ionospheric and solar wind contributions to dispersion and scintillation. Many pulsar timing programs exclude observations when the Sun-pulsar angular separation falls below a threshold (typically 15–30°). This guide shows how to compute and visualise this separation.

## Basic Concept

The angular separation between two sky positions is computed via spherical trigonometry. Astropy's `SkyCoord.separation()` method handles this directly.

## Minimal Example

```python
from astropy.coordinates import SkyCoord, EarthLocation, get_body, solar_system_ephemeris
from astropy.time import Time
import astropy.units as u

# Pulsar coordinates (e.g., J1909-3744)
psr = SkyCoord(ra=287.447644*u.deg, dec=-37.737352*u.deg, frame='icrs')

# Observer location (needed for topocentric solar position)
loc = EarthLocation.of_site('MeerKAT')

# Time of observation
t = Time("2025-01-15 12:00:00")

# Get solar position
with solar_system_ephemeris.set('builtin'):
    sun = get_body('sun', t, loc)
    sun = SkyCoord(sun.ra, sun.dec, frame='icrs')

# Compute separation
sep = psr.separation(sun)
print(f"Sun-pulsar separation: {sep.deg:.2f}°")
```

## Computing Separation Over a Year

```python
import numpy as np
import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord, EarthLocation, get_body, solar_system_ephemeris
from astropy.time import Time
import astropy.units as u

# Pulsar coordinates
psr_name = "J1909-3744"
psr = SkyCoord(ra=287.447644*u.deg, dec=-37.737352*u.deg, frame='icrs')

# Observer location
loc = EarthLocation.of_site('MeerKAT')

# Time array: 1 year, daily sampling
t0 = Time("2025-01-01 00:00:00")
times = t0 + np.arange(365) * u.day

# Compute solar position and separation for each day
sep_angles = []
sun_ra = []
sun_dec = []

with solar_system_ephemeris.set('builtin'):
    for t in times:
        sun = get_body('sun', t, loc)
        sun = SkyCoord(sun.ra, sun.dec, frame='icrs')
        sun_ra.append(sun.ra.deg)
        sun_dec.append(sun.dec.deg)
        sep_angles.append(psr.separation(sun).deg)

sep_angles = np.array(sep_angles)
sun_ra = np.array(sun_ra)
sun_dec = np.array(sun_dec)
```

## Vectorised Version (Faster)

For better performance, pass the full time array at once:

```python
with solar_system_ephemeris.set('builtin'):
    sun = get_body('sun', times, loc)
    sun = SkyCoord(sun.ra, sun.dec, frame='icrs')
    sep_angles = psr.separation(sun).deg
    sun_ra = sun.ra.deg
    sun_dec = sun.dec.deg
```

## Visualisation

```python
fig, axes = plt.subplots(2, 1, figsize=(10, 8))

# Panel 1: Sky map showing pulsar and ecliptic
ax1 = axes[0]
ax1.plot(sun_ra / 15, sun_dec, 'y-', lw=2, label='Ecliptic (Sun path)')
ax1.plot(psr.ra.deg / 15, psr.dec.deg, 'r*', ms=12, label=psr_name)
ax1.set_xlabel('RA [hours]')
ax1.set_ylabel('Dec [deg]')
ax1.set_xlim(0, 24)
ax1.set_ylim(-90, 30)
ax1.legend()
ax1.grid(alpha=0.3)

# Panel 2: Separation angle vs time
ax2 = axes[1]
ax2.plot(times.datetime, sep_angles, 'b-', label=f'{psr_name} separation')
ax2.axhline(20, color='r', ls='--', label='20° cutoff')
ax2.set_xlabel('Date')
ax2.set_ylabel('Sun-Pulsar Separation [deg]')
ax2.legend()
ax2.grid(alpha=0.3)
fig.autofmt_xdate()

plt.tight_layout()
plt.savefig(f'{psr_name}_solar_separation.png', dpi=150)
plt.show()
```

## Finding Solar Conjunction Dates

Identify when the pulsar is within the exclusion zone:

```python
cutoff = 20  # degrees
in_exclusion = sep_angles < cutoff

if np.any(in_exclusion):
    exclusion_times = times[in_exclusion]
    print(f"Pulsar within {cutoff}° of Sun:")
    print(f"  Start: {exclusion_times[0].iso}")
    print(f"  End:   {exclusion_times[-1].iso}")
    print(f"  Duration: {len(exclusion_times)} days")
    
    # Minimum separation (conjunction)
    min_idx = np.argmin(sep_angles)
    print(f"  Closest approach: {sep_angles[min_idx]:.1f}° on {times[min_idx].iso[:10]}")
else:
    print(f"Pulsar always >{cutoff}° from Sun")
```

## Multiple Pulsars

```python
pulsars = {
    'J1909-3744': SkyCoord(ra=287.447644*u.deg, dec=-37.737352*u.deg),
    'J0437-4715': SkyCoord(ra=69.3167*u.deg, dec=-47.2525*u.deg),
    'J1713+0747': SkyCoord(ra=258.4150*u.deg, dec=7.7878*u.deg),
}

with solar_system_ephemeris.set('builtin'):
    sun = get_body('sun', times, loc)
    sun = SkyCoord(sun.ra, sun.dec, frame='icrs')
    
    plt.figure(figsize=(12, 5))
    for name, psr in pulsars.items():
        sep = psr.separation(sun).deg
        plt.plot(times.datetime, sep, label=name)
    
    plt.axhline(20, color='r', ls='--', alpha=0.5, label='20° cutoff')
    plt.xlabel('Date')
    plt.ylabel('Sun-Pulsar Separation [deg]')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()
```

## Notes

- The `'builtin'` ephemeris is sufficient for ~arcminute accuracy. For higher precision, use `'de430'` (requires `jplephem` package).
- Solar elongation varies annually as Earth orbits the Sun; pulsars near the ecliptic have closer conjunctions.
- The observer location affects the topocentric solar position slightly but is negligible for angular separation calculations at the degree level.
