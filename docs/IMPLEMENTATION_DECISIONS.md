# Implementation Decisions: SkyTrace Scientific Integrity & Engineering Fixes

## 1. Verified Repository and Astronomical Facts

1. **Real SPHEREx FITS Product Architecture:**
   - Real Level 2 products present in workspace: `SPHERExLVFSurveyData/level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits` (71,634,240 bytes) and cached/sample files.
   - HDU Structure:
     - `HDU 0: PRIMARY`: Header-only, contains software pipeline version (`VERSION = '6.4+psffix1'`).
     - `HDU 1: IMAGE`: 2D float32 image array (2040x2040). Header contains `OBSID` (e.g. `2025W28_1B_0480_4`), `EXPIDN` (e.g. `202528102048041`), `DETECTOR` (1-6), `BUNIT` ('MJy / sr'), full celestial WCS (`CTYPE = 'RA---TAN-SIP' / 'DEC--TAN-SIP'`, order-3 SIP polynomials `A_ORDER`, `B_ORDER`, `AP_ORDER`, `BP_ORDER`), `DATE-OBS`, `MJD-OBS`, `MJD-BEG`, `MJD-AVG`, `MJD-END`, `XPOSURE` (113.58s), `TIMESYS='UTC'`, `RADESYS='ICRS'`.
     - `HDU 2: FLAGS`: 2D int32 bitmask array (2040x2040). Bit definitions explicitly given in header cards: `MP_TRANSIENT=0`, `MP_OVERFLOW=1`, `MP_SUR_ERROR=2`, `MP_PHANTOM=4`, `MP_REFERENCE=5`, `MP_NONFUNC=6`, `MP_DICHROIC=7`, `MP_MISSING_DATA=9`, `MP_HOT=10`, `MP_COLD=11`, `MP_FULLSAMPLE=12`, `MP_PHANMISS=14`, `MP_NONLINEAR=15`, `MP_PERSIST=17`, `MP_OUTLIER=19`, `MP_SOURCE=21`.
     - `HDU 3: VARIANCE`: 2D float32 variance array (2040x2040), `BUNIT = 'MJy2 / sr2'`, `UTYPE = 'VarianceUncertainty'`, matching WCS.
     - `HDU 4: ZODI`: 2D float32 model zodiacal light array.
     - `HDU 5: PSF`: 3D float32 array (101x101x121) reconstructed PSF grid.
     - `HDU 6: WCS-WAVE`: BinTableHDU (1 row x 3 columns: `X` 9-element array, `Y` 9-element array, `VALUES` 2x9x9 array giving central wavelength and bandwidth in microns across the detector grid, referenced by `CTYPE1W = 'WAVE-TAB'`, `CTYPE2W = 'WAVE-TAB'`).
   - The science product itself contains `WCS-WAVE` for per-pixel wavelength and bandwidth interpolation! Standalone calibration files (such as `spectral_wcs_*.fits`) contain full per-pixel `CWAVE` and `CBAND` arrays, but for Level 2 images, `WCS-WAVE` provides tabular bivariate lookup $(x, y) \to (\lambda, \Delta\lambda)$ directly in HDU 6.

2. **Archive Discovery & Network Behavior:**
   - In sandboxed environments without direct external network egress, network requests to `https://irsa.ipac.caltech.edu/TAP` fail cleanly with hostname resolution errors (`socket.gaierror: [Errno 8]`).
   - DataLink files saved previously (e.g. `spherex_2025W46_2A_0217_3.fits` and `spherex_2025W23_2B_0291_1.fits`) are XML VOTables containing DataLink service descriptions with `#this` (direct FITS url), `#cutout` (IBE cutout service), and `#calibration` URLs.
   - The archive fallback in `irsa_client.py` was hardcoded to 7 fabricated/misrepresented records and copied files arbitrarily onto other observation IDs. This must be eliminated.

3. **Existing Tracking & State Issues:**
   - `trajectory_service.py` and `matching_service.py` both implement competing tracking logic. Both contained fallbacks `ref_source = ref_sources_resp.sources[0]` if the requested reference source was not found.
   - An arbitrary astrometric systematic floor `0.15` arcsec was hardcoded without calibration provenance.
   - Degree-of-freedom and reduced $\chi^2$ calculations were reported even for 2-epoch fits where $df = 0$.
   - React frontend reset active epoch to E0 on track completion and initiated tracking automatically upon source selection without explicit track intent.
   - Unused dependency `react-zoom-pan-pinch` was present in `package-lock.json` but not declared in `package.json` nor imported in source.

---

## 2. Comparison of Approaches

### (A) Supplied Runbook
- Thorough, rigorous scientific audit covering Phase 0A through Phase 6 in sequential order.
- Highly detailed requirements on provenance, astrometry, WCS, download security, and undo/redo.
- *Strength:* Scientifically uncompromising; directly tackles fabricated data and fake physics.
- *Limitation:* If treated as a pure sequential waterfall, frontend integration and challenge usability could be delayed until backend perfection.

### (B) Independent Rapid-Delivery Plan
- Focus heavily on getting the UI interactive and eliminating the immediate runtime crashes and fabricated records.
- *Strength:* Fast user-facing delivery for the Space Apps Challenge context.
- *Limitation:* May leave subtle scientific regressions (e.g., ad-hoc WCS approximations, incorrect dof math, or unvalidated cache entries).

### (C) Adopted Reasoned Hybrid Plan
We adopt the **Supplied Runbook's rigorous scientific foundation and execution sequence** while structuring the backend and frontend services so that each phase produces verifiable working software with regression tests:
1. **Phase 0A & 0B (Immediate Data Integrity):** Discover IRSA schema/scripts, remove fabricated fallbacks, create atomic verified `cache_index.py`, enforce strict URL allowlists and streaming validation, eliminate `sources[0]` fallbacks, and fix prediction verification.
2. **Phase 1 (Astrometry, WCS, Spectroscopy, Timeline):** Implement backend WCS projection endpoint (`POST /observations/{observation_id}/project`), replace linear wavelength approximations with bivariate lookup from `WCS-WAVE`, group epochs by authentic visit identity (`EXPIDN`/`OBSID`), and fix frontend state handling (explicit track action, persistent tracks, no unwanted epoch reset).
3. **Phase 3 (Unified Tracker, Ambiguity & Undo/Redo):** Consolidate `trajectory_service` and `matching_service` into a single authoritative tracker service; introduce deterministic source hashing (`src_{obs_id}_{x}_{y}`); implement per-track append-only update logs with durable file persistence (`backend/data/tracks.json`) supporting undo and redo. Implement scientific forced photometry using `IMAGE`, `VARIANCE`, and `FLAGS` HDUs.
4. **Phase 4 (Statistically Defensible Fitting & Classification):** Tangent-plane projection relative to reference coordinate; rigorous degrees-of-freedom ($2n-4$ for linear, 0 for 2-epoch displacement); velocity covariance & significance; distinct separation of association state (`match`, `ambiguous`, `no_match`, `outside_coverage`, `unknown_coverage`) from overall track classification (`INSUFFICIENT_DATA`, `AMBIGUOUS`, `STATIC_SOURCE`, `HIGH_CONFIDENCE_MOTION`).
5. **Phase 2 (Scientific Comparison Modes):** Blink, Side-by-side with synchronized sky coordinates, Opacity overlay, and gated difference imaging (refusing incompatible pairs with clear scientific rationale).
6. **Phase 5 (Association Inspector, Export, Known Objects):** Add proposal inspector ("Why was this matched?"), JSON and CSV export distinguishing `measured | fitted | predicted | missing`, remove arbitrary 1.5"/day prediction default, integrate Astroquery IRSA MOST.
7. **Phase 6 (Hardening & Documentation):** Reconcile lockfile, remove wildcard CORS with credentials, calibrate error handling, correct annual parallax formulation in `docs/SCIENTIFIC_METHODS.md`.

---

## 3. Deviations & Material Decisions

1. **Wavelength Calibration Source:**
   - Discovery of the local authentic SPHEREx Level 2 FITS file reveals that `WCS-WAVE` is embedded directly in HDU 6 as a FITS tabular coordinate lookup table (`CTYPE1W = 'WAVE-TAB'`, `CTYPE2W = 'WAVE-TAB'`). We implement bivariate bilinear interpolation over the $(X, Y)$ control points from this HDU for the primary image, while supporting external calibration products when present.
2. **Offline & Network Gating:**
   - Since sandbox network restrictions may block live IPAC TAP queries, all tests requiring live network access are marked with `@pytest.mark.real_data` and conditionally skipped if network resolution fails, while offline searches are strictly backed by the authentic local verified cache index without returning fabricated records.
3. **Durable Track Storage:**
   - Tracks and undo/redo histories will be persisted atomically to `backend/data/tracks.json` with write-to-temp-and-rename semantics to ensure survival across process restarts.
