# SkyTrace: Astronomical Data Sources & Archive Provenance

## Primary Mission: NASA SPHEREx
**SPHEREx** (Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer) is an all-sky spectral survey mission operated by NASA / JPL-Caltech.

### 1. Official Archive Access
Scientific data products are archived and served publicly by the **NASA/IPAC Infrared Science Archive (IRSA)**:
- **IRSA SPHEREx Landing Page:** [https://irsa.ipac.caltech.edu/Missions/spherex.html](https://irsa.ipac.caltech.edu/Missions/spherex.html)
- **SPHEREx Data Explorer:** [https://irsa.ipac.caltech.edu/applications/spherex/](https://irsa.ipac.caltech.edu/applications/spherex/)
- **Data Product Documentation:** [https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/)
- **Data Access Guide:** [https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)

### 2. Programmatic IVOA TAP & SIAv2 Services
SkyTrace connects directly to official IVOA Table Access Protocol (TAP) endpoints:
- **TAP Service Base URL:** `https://irsa.ipac.caltech.edu/TAP`
- **ObsCore Catalog Table:** `spherex.obscore`
- **Supported Query Syntax:** Astronomical Data Query Language (ADQL 2.0)
- **Spatial Geometry:** `CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE('ICRS', ra, dec, radius))`
- **Datalink Endpoint:** `https://irsa.ipac.caltech.edu/datalink/links/spherex?ID=...`

### 3. SPHEREx Calibrated Spectral Image Structure (Level 2/3)
Authentic SPHEREx FITS products contain multi-extension arrays:
1. `PRIMARY`: Header-only HDU with observatory, pointing, and execution metadata.
2. `IMAGE` / `SCI`: 2D floating-point scientific surface brightness array (units: `MJy/sr`).
3. `FLAGS`: 2D bitmask array flagging saturated pixels, cosmic rays, and edge artifacts.
4. `VARIANCE` / `VAR`: 2D variance array ($\sigma^2$) for measurement error propagation.
5. `ZODI`: Model zodiacal light background foreground subtraction.
6. `PSF`: Position-dependent Point Spread Function grid.
7. `WCS-WAVE`: Spectral WCS mapping pixel dispersion coordinates to central wavelengths.

### 4. Instrument Bands & Linear Variable Filters (LVF)
SPHEREx mounts 6 focal plane arrays, each filtered by a Linear Variable Filter:
- **Band 1 (D1):** 0.75 – 1.11 µm
- **Band 2 (D2):** 1.11 – 1.64 µm
- **Band 3 (D3):** 1.64 – 2.42 µm
- **Band 4 (D4):** 2.42 – 3.82 µm
- **Band 5 (D5):** 3.82 – 4.42 µm
- **Band 6 (D6):** 4.42 – 5.00 µm

Spatial resolution is approximately **6.2 arcseconds per pixel**.

### 5. Synthetic Demonstration Mode
When operating without an internet connection or for interface onboarding, SkyTrace generates simulated multi-epoch FITS arrays with:
- True SPHEREx pixel scale (6.2″/px) and tangent projection WCS
- Gaussian point sources and realistic infrared background noise
- Explicitly tagged FITS header comment: `SIMULATED DEMO — NOT REAL SPHEREx DATA`
- Visual beacon in the application header alerting the user to synthetic data.
