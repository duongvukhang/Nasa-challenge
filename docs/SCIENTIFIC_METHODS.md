# SkyTrace: Scientific Methodology & Mathematical Formulations

## 1. Astronomical Source Detection
SkyTrace detects point-like sources in calibrated SPHEREx FITS images using the DAOStarFinder algorithm (`photutils.detection.DAOStarFinder`):

### Background Estimation & Noise
Local background intensity $\mu_{bkg}$ and dispersion $\sigma_{bkg}$ are computed using iterative sigma-clipped statistics:
$$\mu_{bkg}, \sigma_{bkg} = \text{sigma\_clipped\_stats}(I_{finite}, \sigma=3.0, \text{maxiters}=5)$$

A pixel is flagged as a candidate source centroid if its background-subtracted intensity exceeds a user-specified threshold:
$$I(x, y) - \mu_{bkg} \ge N_{\sigma} \cdot \sigma_{bkg}$$

### Centroid & Uncertainty
Centroids $(x_c, y_c)$ are determined by 2D Gaussian fitting over the PSF kernel width (nominal SPHEREx FWHM $\approx 3.0$ pixels). Astrometric positional uncertainty is modeled as:
$$\sigma_{pos} \approx \frac{\text{FWHM}}{2 \cdot \text{SNR}} \cdot s_{pix}$$
where $s_{pix}$ is the plate scale ($\approx 6.16$ arcsec/pixel) and $\text{SNR} = I_{peak} / \sigma_{bkg}$.

---

## 2. Astrometry and World Coordinate System (WCS)
Pixel coordinates $(x, y)$ are projected onto celestial coordinates $(\alpha, \delta)$ (Right Ascension and Declination, J2000 ICRS) via the FITS WCS standard:
$$(\alpha, \delta) = \mathcal{W}(x, y; \text{CRVAL}, \text{CRPIX}, \text{CDELT}, \text{CTYPE})$$
SkyTrace uses Astropy's `astropy.wcs.WCS` engine. If celestial WCS keywords are missing from the header, coordinate tracking is disabled rather than fabricated.

---

## 3. Cross-Epoch Source Matching & Confidence Scoring
To track an astronomical source across observations separated in time, candidate sources within a search radius $\theta_{match}$ (default $3.0^{\prime\prime}$) are evaluated using their great-circle separation $\theta$:
$$\theta = \arccos\left(\sin \delta_1 \sin \delta_2 + \cos \delta_1 \cos \delta_2 \cos(\alpha_1 - \alpha_2)\right)$$

Normalized astrometric separation is defined as:
$$\chi = \frac{\theta}{\sqrt{\sigma_{ref}^2 + \sigma_{cand}^2}}$$

### Match Status Classification:
1. **Likely Match:** Exactly one candidate within $\theta_{match}$ satisfying $\chi \le 2.5$.
2. **Ambiguous Match:** Multiple candidates detected within $\theta_{match}$, or separation falls in $2.5 < \chi \le 4.0$.
3. **Not Detected:** Target coordinates fall within the observed field of view, but no source exceeds the detection threshold.
4. **Insufficient Data:** Target coordinates lie outside the detector footprint or celestial WCS is unavailable.

### Heuristic Confidence Score:
$$\mathcal{S} = 0.7 \cdot \exp\left(-\frac{\chi^2}{2}\right) + 0.3 \cdot \min\left(1.0, \frac{\text{SNR}}{10.0}\right)$$
This value is an empirical matching metric in $[0.0, 1.0]$ and is not claimed to be a calibrated Bayesian posterior probability.

---

## 4. Infrared Spectrophotometry (Linear Variable Filters)
SPHEREx measures infrared light using Linear Variable Filters (LVF). In each detector array, the passband wavelength varies continuously across the dispersion axis:
$$\lambda(x) \approx \lambda_{min} + \frac{x}{N_x - 1} (\lambda_{max} - \lambda_{min})$$
When a source is identified in multiple pointings or across detector arrays (Bands 1 through 6), measurements are compiled into an infrared Spectral Energy Distribution (SED) across $0.75 \le \lambda \le 5.00\,\mu\text{m}$.

---

## 5. Kinematic Motion Prediction & Physical Limitations
SkyTrace provides a short-term angular extrapolation baseline:
$$\alpha(t) = \alpha(t_0) + \frac{\mu_{\alpha*} \cdot (t - t_0)}{\cos \delta(t_0)}$$
$$\delta(t) = \delta(t_0) + \mu_{\delta} \cdot (t - t_0)$$
$$\sigma_{pred}(t) = \sigma_0 + \dot{\sigma} \cdot |t - t_0|$$

### Explicit Physical Limitations:
1. **No Keplerian Gravity:** Linear extrapolation assumes constant apparent sky velocity and does not account for gravitational orbital mechanics.
2. **Parallactic Motion Omitted:** Trans-Neptunian Objects and hypothetical Planet X candidates exhibit substantial annual reflex parallax caused by Earth's orbit around the Sun ($\sim \pm 3600^{\prime\prime} / d_{\text{AU}}$).
3. **Validation Role:** Predictions serve as an illustrative baseline to compare against subsequent observations ($\chi_{residual} = \Delta \theta / \sigma_{pred}$).
