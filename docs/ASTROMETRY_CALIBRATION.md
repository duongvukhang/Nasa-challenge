# SPHEREx Astrometry & Calibration Notes

## Overview
This document specifies the coordinate transformation and astrometric uncertainty models employed by SkyTrace for multi-epoch SPHEREx observations.

## Astrometric Systematics Disclaimer
> **Important:** Centroid uncertainty only; astrometric systematics not calibrated.

- **Positional Centroid Uncertainty:** Positional uncertainties reported for detected sources ($\sigma_{\text{pos}}$) are estimated from local Gaussian or point-spread-function centroid fitting based on signal-to-noise ratio ($\text{SNR}$) and detector point spread function ($\text{FWHM}$):
  $$\sigma_{\text{centroid}} \approx \frac{\text{FWHM}}{2.355 \times \text{SNR}}$$
  with an empirical measurement floor ($\sigma_{\text{floor}} = 0.15^{\prime\prime} \approx 0.024\text{ pixel}$).
- **Instrumental Distortion & WCS:** Celestial transformations use official Astropy WCS parsing of the FITS header keywords (`CRVAL`, `CRPIX`, `CDELT`, `PC`, and SIP polynomial distortion coefficients `A_*`, `B_*`, `AP_*`, `BP_*` when present in Level 2 products).
- **Astrometric Systematics:** Large-scale focal-plane distortions, thermal drift, spacecraft jitter, and band-to-band chromatic differential refraction across the 102 Linear Variable Filter (LVF) bands are not independently solved in SkyTrace. Absolute astrometric alignment between distant epochs relies entirely on the mission Level 2 pipeline astrometric solution.

## Fitting Math & Degrees of Freedom
1. **Tangent-Plane Projection:**
   For any candidate track across multiple epochs, spherical coordinates $(\alpha, \delta)$ are projected onto a local tangent plane centered at the reference epoch $E_0 = (\alpha_0, \delta_0)$ using Astropy's `spherical_offsets_to`, avoiding coordinate singularity or artificial distortion near the celestial poles and across the $\alpha = 0^\circ / 360^\circ$ boundary.
2. **Degrees of Freedom ($df$):**
   - For $N_{\text{det}} = 2$ detections:
     $N_{\text{meas}} = 4$ measurements ($x_1, y_1, x_2, y_2$), $N_{\text{param}} = 4$ ($x_0, y_0, v_x, v_y$).
     Degrees of freedom $df = 4 - 4 = 0$.
     Two detections establish apparent displacement only, but $df = 0$. Reduced $\chi^2$ is mathematically undefined (`None`). Linear kinematics cannot be independently verified without a 3rd observation epoch.
   - For $N_{\text{det}} \ge 3$ detections:
     Linear motion model has $df = 2 N_{\text{det}} - 4 \ge 2$.
     Stationary source model has $df = 2 N_{\text{det}} - 2 \ge 4$.
3. **Velocity Significance:**
   Parameters $v_x, v_y$ and their covariance matrix $\mathbf{C}$ are computed via weighted least-squares regression.
   Velocity uncertainty:
   $$\sigma_v = \frac{\sqrt{(v_x \sigma_{v_x})^2 + (v_y \sigma_{v_y})^2}}{v}$$
   If velocity significance $\frac{v}{\sigma_v} < 3.0$, the apparent motion is kinematically indistinguishable from zero at $3\sigma$ confidence, and the source is assessed as stationary.
