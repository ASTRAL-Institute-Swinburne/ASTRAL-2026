# Spinifex: Ionospheric Rotation Measure Calculations

## What is Spinifex?

Spinifex is a pure Python package for ionospheric analyses in radio astronomy. Its primary function is calculating the **ionospheric contribution to Faraday rotation** (rotation measure, RM) along a given line of sight.

Spinifex is a modern rewrite of [RMextract](https://github.com/maaijke/RMextract) (Mevius 2018), with improved Python integration and additional features. It combines:

- **IONEX data**: Global ionospheric TEC maps from GNSS networks
- **IGRF**: International Geomagnetic Reference Field (via `ppigrf`)
- **IRI**: International Reference Ionosphere (via `PyIRI`)

The name comes from spinifex grass native to Australia—the "spines" are reminiscent of ionospheric pierce points, and "spin" relates to Faraday rotation.

## Why Do We Need This?

Radio waves passing through the ionosphere experience **Faraday rotation** due to the magnetised plasma. The rotation measure is:

$$\mathrm{RM_{iono}} = \frac{e^3}{2\pi m_e^2 c^4} \int_{\mathrm{iono}} n_e \, \mathbf{B} \cdot d\mathbf{l}$$

For pulsar timing and polarimetry, we often need to subtract this ionospheric contribution to isolate the interstellar RM. Spinifex predicts RM_iono using global TEC maps and geomagnetic field models.

## Installation

```bash
pip install spinifex
```

## Basic Usage

### Core Function: `get_rm_from_skycoord`

```python
from spinifex import get_rm
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.time import Time
import astropy.units as u
import numpy as np
from pathlib import Path

# Define your telescope location
meerkat = EarthLocation(
    lon=21.443889*u.deg,
    lat=-30.711056*u.deg, 
    height=1086.6*u.m
)

# Define your source coordinates
source = SkyCoord(ra=287.447644*u.deg, dec=-37.737352*u.deg)

# Define observation times
times = Time("2025-01-15T00:00:00") + np.arange(10) * 15*u.min

# Calculate ionospheric RM
result = get_rm.get_rm_from_skycoord(
    loc=meerkat,
    times=times,
    source=source,
    server='chapman',
    prefix='uqr',
    output_directory=Path('./ionex_cache')
)
```

### Understanding the Parameters

| Parameter | Description |
|-----------|-------------|
| `loc` | Telescope location as `EarthLocation` |
| `times` | Observation times as `Time` object (single or array) |
| `source` | Source coordinates as `SkyCoord` |
| `server` | IONEX data server (`'chapman'` recommended) |
| `prefix` | IONEX product type (`'uqr'` = UPC rapid, 15-min resolution) |
| `output_directory` | Local cache for downloaded IONEX files |

### The Result Object

The returned object contains:

| Attribute | Description |
|-----------|-------------|
| `result.rm` | Ionospheric RM values (rad/m²) |
| `result.rm_error` | RM uncertainties |
| `result.times` | Corresponding timestamps |
| `result.azimuth` | Source azimuth at each time |
| `result.elevation` | Source elevation at each time |

### Printing Results

```python
print("Time                     RM (rad/m²)   Az(°)   El(°)")
for rm, tm, az, el in zip(result.rm, result.times, result.azimuth, result.elevation):
    print(f"{tm.isot} {rm:7.4f}   {az:6.2f}  {el:5.2f}")
```

## IONEX Data Sources

Spinifex downloads IONEX (IONosphere map EXchange) files automatically. Common options:

| Server | Prefix | Description | Resolution |
|--------|--------|-------------|------------|
| `chapman` | `uqr` | UPC rapid TEC maps | 15 min |
| `chapman` | `uqrg` | UPC rapid global | 15 min |
| `cddis` | `jplg` | JPL final | 2 hours |
| `cddis` | `igsg` | IGS combined | 2 hours |

**Note**: CDDIS requires NASA Earthdata authentication (see below). The Chapman server (`chapman.upc.es`) provides free access to UPC products.

## Practical Example: Correcting Pulsar RM Measurements

```python
import pandas as pd
import numpy as np
from astropy.time import Time
from astropy.coordinates import EarthLocation, SkyCoord
import astropy.units as u
from spinifex import get_rm
from pathlib import Path

# Setup
meerkat = EarthLocation(lon=21.443889*u.deg, lat=-30.711056*u.deg, height=1086.6*u.m)
source = SkyCoord(ra=287.447644*u.deg, dec=-37.737352*u.deg)

# Load your observations
df = pd.read_csv('pulsar_observations.csv')
obs_times = Time(pd.to_datetime(df['UTC Start']))

# Get ionospheric RM for each observation
iono_rms = []
iono_errors = []

for t in obs_times:
    try:
        result = get_rm.get_rm_from_skycoord(
            loc=meerkat,
            times=t,
            source=source,
            server='chapman',
            prefix='uqr',
            output_directory=Path('./ionex_cache')
        )
        iono_rms.append(result.rm[0])
        iono_errors.append(result.rm_error[0])
        print(f"✓ {t.iso}: RM = {result.rm[0]:.3f} rad/m²")
    except Exception as e:
        print(f"✗ {t.iso}: {e}")
        iono_rms.append(np.nan)
        iono_errors.append(np.nan)

# Add to dataframe
df['Iono_RM'] = iono_rms
df['Iono_RM_error'] = iono_errors

# Compute ISM RM (measured - ionospheric)
df['ISM_RM'] = df['Measured_RM'] - df['Iono_RM']
```

## Caching IONEX Files

Spinifex downloads IONEX files on demand. Using `output_directory` caches them locally to avoid re-downloading:

```python
output_directory=Path('./ionex_cache')
```

Each day's data is ~1-2 MB compressed. For large datasets, pre-download the files you need.

## CDDIS Authentication (if needed)

For JPL/IGS products from CDDIS, you need NASA Earthdata credentials:

1. Create account at: https://urs.earthdata.nasa.gov/
2. Create `~/.netrc` file:
   ```
   machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
   ```

For most applications, the Chapman server with UPC products (`server='chapman'`, `prefix='uqr'`) works well without authentication.

## Tips

1. **Use the cache**: Always specify `output_directory` to avoid redundant downloads
2. **Batch processing**: Pass arrays of times rather than looping for better efficiency
3. **Check elevation**: Low-elevation observations have larger ionospheric path lengths and higher RM
4. **Time resolution**: UPC rapid products (15 min) capture diurnal variations better than 2-hour products

## Further Reading

- [Spinifex documentation](https://spinifex.readthedocs.io/)
- [Sotomayor-Beltran et al. (2013)](https://ui.adsabs.harvard.edu/abs/2013A%26A...552A..58S) — ionFR methodology
- [Mevius (2018)](https://github.com/maaijke/RMextract) — RMextract (predecessor)
