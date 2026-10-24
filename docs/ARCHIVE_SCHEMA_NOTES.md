# SPHEREx IRSA Archive & Data Product Schema Notes

## 1. Archive Access Protocols & TAP Schema

### 1.1 TAP Endpoint & Table
- **Service Endpoint:** `https://irsa.ipac.caltech.edu/TAP`
- **Primary ObsCore Table:** `spherex.obscore`
- **Key Columns:**
  - `obs_id`: Primary product identifier (e.g., `2025W28_1B_0480_4` or `2025W18_1B_0001_1_D1`).
  - `s_ra`, `s_dec`: Pointing center coordinates in degrees (ICRS).
  - `s_region`: Spherical polygon footprint of the detector field on the celestial sphere.
  - `access_url`: Direct URL to DataLink document or FITS science product.
  - `access_format`: `application/x-votable+xml;content=datalink` or `image/fits`.
  - `energy_bandpassname`: Bandpass identifier (e.g., `D1`, `D2`, ..., `D6` or `LVF1`...`LVF6`).
  - `em_min`, `em_max`: Spectral interval in meters ($0.75 \times 10^{-6}$ to $5.0 \times 10^{-6}$ m).
  - `t_min`, `t_max`: Observation interval in MJD UTC.
  - `t_exptime`: Exposure duration in seconds (~113.6 s for nominal L2 survey visits).
  - `dataproduct_type`: `image`.
  - `obs_release_date`: Release name/date (e.g., QR2, QR3).

### 1.2 Footprint vs. Center ADQL Semantics
- Center-only cone search (`CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE(...))`) fails to match observations where the search target lies inside the 3.5° footprint but away from the field center.
- Where supported by the TAP geometry engine, full footprint intersection must be used:
  ```sql
  INTERSECTS(CIRCLE('ICRS', {ra}, {dec}, {radius_deg}), s_region) = 1
  ```
  with interval overlap:
  ```sql
  t_max >= {start_mjd} AND t_min <= {end_mjd}
  ```

### 1.3 DataLink Structure
When `access_format` is DataLink, the response is an IVOA VOTable XML containing:
- `#this`: Direct download URL for the Level 2 science FITS product.
- `#cutout`: Caltech/IPAC Image Box Extraction (IBE) cutout service URL (`https://irsa.ipac.caltech.edu/ibe/cutout`).
- `#calibration`: Calibration FITS files (`abs_gain_matrix`, `nonlinear_pars`, `dark`, `dichroic`, `spectral_wcs`).

---

## 2. Authentic SPHEREx Level 2 FITS Product Structure

Inspected from authentic Level 2 FITS file (`level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits`, 71,634,240 bytes):

| HDU Index | Extension Name | Type | Shape | Data Type | Purpose & Units |
|---|---|---|---|---|---|
| 0 | `PRIMARY` | PrimaryHDU | (none) | N/A | Pipeline version metadata (`VERSION='6.4+psffix1'`) |
| 1 | `IMAGE` | ImageHDU | (2040, 2040) | `float32` | Calibrated surface brightness (`BUNIT = 'MJy / sr'`) |
| 2 | `FLAGS` | ImageHDU | (2040, 2040) | `int32` | Data quality bitmask (dimensionless) |
| 3 | `VARIANCE` | ImageHDU | (2040, 2040) | `float32` | Per-pixel statistical variance (`BUNIT = 'MJy2 / sr2'`) |
| 4 | `ZODI` | ImageHDU | (2040, 2040) | `float32` | Zodiacal light model (`BUNIT = 'MJy / sr'`) |
| 5 | `PSF` | ImageHDU | (121, 101, 101) | `float32` | 3D exposure-averaged PSF reconstruction grid |
| 6 | `WCS-WAVE` | BinTableHDU | (1 row, 3 cols) | Binary table | Bivariate $(x, y) \to (\lambda, \Delta\lambda)$ lookup table in microns |

### 2.1 Critical Header Keywords in HDU 1 (`IMAGE`)
- `OBSID`: Unique Observation ID (e.g. `'2025W28_1B_0480_4'`).
- `EXPIDN`: Unique Integer Exposure ID (e.g. `202528102048041`).
- `DETECTOR`: Detector index (`1` to `6`). Detectors 1–3 are SWIR (0.75–2.42 $\mu$m); detectors 4–6 are MWIR (2.42–5.00 $\mu$m).
- `DATE-OBS`: ISO-8601 observation start timestamp.
- `MJD-OBS`: Modified Julian Date of observation start.
- `DATE-AVG` / `MJD-AVG`: Midpoint of exposure (used for astrometric timing).
- `XPOSURE`: Integration duration in seconds (~113.58 s).
- `RADESYS`: `'ICRS'`.
- `CTYPE1` / `CTYPE2`: `'RA---TAN-SIP'` / `'DEC--TAN-SIP'`.
- `A_ORDER`, `B_ORDER`, `AP_ORDER`, `BP_ORDER`: Order-3 SIP distortion polynomial coefficients.
- `CRVAL1`, `CRVAL2`: Reference sky coordinates in degrees.
- `CRPIX1`, `CRPIX2`: Reference pixel coordinates (usually `1020.5`, `1020.5`).

### 2.2 Data Quality Bitmask Flags (HDU 2 `FLAGS`)
- Bit 0 (`MP_TRANSIENT`): Transient detected during Sample-Up-the-Ramp (SUR).
- Bit 1 (`MP_OVERFLOW`): Detector overflow/saturation.
- Bit 2 (`MP_SUR_ERROR`): Onboard processing calculation error.
- Bit 4 (`MP_PHANTOM`): Phantom pixel.
- Bit 5 (`MP_REFERENCE`): Non-illuminated reference pixel.
- Bit 6 (`MP_NONFUNC`): Permanently non-functional/dead pixel.
- Bit 7 (`MP_DICHROIC`): Low optical efficiency.
- Bit 9 (`MP_MISSING_DATA`): Missing telemetry packets.
- Bit 10 (`MP_HOT`): Hot pixel.
- Bit 11 (`MP_COLD`): Cold pixel.
- Bit 15 (`MP_NONLINEAR`): Nonlinearity correction invalid.
- Bit 17 (`MP_PERSIST`): Persistent charge above threshold.
- Bit 19 (`MP_OUTLIER`): Outlier flagged during processing.
- Bit 21 (`MP_SOURCE`): Pixel associated with known source.

### 2.3 WCS-WAVE Tabular Lookup (HDU 6)
- Control points: $9 \times 9$ spatial grid with `X = [1, 256, 511, 766, 1021, 1275, 1530, 1785, 2040]` and `Y = [1, 256, 511, 766, 1021, 1275, 1530, 1785, 2040]`.
- Output array: `VALUES` of shape `(9, 9, 2)`.
  - Slice `VALUES[:, :, 0]`: Central wavelength $\lambda$ in microns.
  - Slice `VALUES[:, :, 1]`: Channel bandwidth $\Delta\lambda$ in microns.
- Bilinear interpolation over this $9 \times 9$ mesh provides calibrated per-pixel wavelength and bandwidth across the focal plane without relying on arbitrary linear approximations.

---

## 3. Environment & Verification Status
- **Live TAP service verification:** In sandbox execution mode with network egress disabled, remote TAP queries return `socket.gaierror`. Verification of live IRSA TAP response is marked **NOT VERIFIED (SANDBOX NETWORK RESTRICTED)**.
- **Local authentic FITS products:** Verified directly against SPHEREx Level 2 products on disk. Verification status: **PASS**.
