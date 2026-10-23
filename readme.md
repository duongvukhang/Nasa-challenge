# SkyTrace — Interactive SPHEREx Infrared Sky Explorer
### 2026 NASA Space Apps Challenge: *Planet X and SPHEREx*
### *Redesigned with a Stellarium Web-Inspired Immersive Experience*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61dafb.svg)](https://react.dev/)
[![Astropy](https://img.shields.io/badge/Astropy-6.0%2B-orange.svg)](https://www.astropy.org/)
[![Photutils](https://img.shields.io/badge/Photutils-1.11%2B-green.svg)](https://photutils.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SkyTrace** is an interactive, public-facing astronomy web application built for the 2026 NASA Space Apps Challenge (*Planet X and SPHEREx*). Inspired by the immersive planetarium design of **Stellarium Web** ([stellarium-web.org](https://stellarium-web.org/)), SkyTrace delivers a nearly full-screen astronomical sky viewer with translucent floating controls, allowing users to explore authentic infrared spectral observations from NASA's **SPHEREx** mission, select celestial sources, track cross-epoch positions over time, analyze Linear Variable Filter (LVF) infrared spectra, and validate kinematic motion predictions.

---

## 🌟 Stellarium-Inspired Visual Design & Layout

Unlike conventional three-column web dashboards, SkyTrace lets the celestial observation occupy nearly the entire viewport:

- **Full-Screen Astronomical Canvas:** Deep space navy and black background (`#030712`) showcasing authentic calibrated SPHEREx FITS images with smooth zooming and panning.
- **Top Floating Omnibox:** Slim glassmorphic toolbar with sidebar toggle, mission badge, live celestial search field (search by source ID or celestial coordinates `RA, Dec`), dynamic Field of View (`FOV 3.5° × 3.5°`), UTC observation timestamp, and fullscreen toggle.
- **Collapsible Left Sidebar:** Translucent slide-out navigation panel with vertical icon strip for **Explore Data**, **View Settings**, **Observations**, and **Information**.
- **Bottom Floating Dock:** Stellarium-style icon dock for toggling observational overlays:
  - Source detection reticles
  - Source identity labels
  - Equatorial coordinate grid (RA/Dec lines)
  - Multi-epoch tracking trajectories
  - Positional uncertainty error ellipses
  - Infrared LVF spectral mode
  - Chronological observation timeline
  - Contrast & brightness display controls
- **Bottom-Right Time Controller:** Compact floating playback widget for navigating actual observation timestamps (previous/next epoch, play/pause, adjustable speed, and epoch scrubber).
- **Floating Source Inspector Card:** Appears when an astronomical source is clicked, presenting astrometric coordinates (decimal & sexagesimal), surface brightness (`MJy/sr`), aperture flux, SNR, and cross-epoch match status without obstructing the sky viewer.
- **Expandable Infrared Spectrum Drawer:** Floating translucent drawer showing Recharts Spectral Energy Distributions (SED) across SPHEREx's 6 LVF channels (0.75 – 5.00 µm).

---

## 🛰️ Scientific Foundation: NASA/IPAC IRSA & SPHEREx
SkyTrace interfaces directly with the official **NASA/IPAC Infrared Science Archive (IRSA)**:
- **IVOA TAP Service:** `https://irsa.ipac.caltech.edu/TAP` (`spherex.obscore`)
- **Datalink Service:** `https://irsa.ipac.caltech.edu/datalink/links/spherex?ID=...`
- **Data Access Documentation:** [caltech-ipac.github.io/spherex-archive-documentation/](https://caltech-ipac.github.io/spherex-archive-documentation/)

> [!IMPORTANT]
> **Scientific Integrity & Planet X:** SkyTrace does not claim to discover Planet X. Point detections represent photometric peaks above background noise, and apparent motion can arise from solar system bodies, high-proper-motion stars, or astrometric jitter. Rigorous physical identification requires multi-observatory orbit solutions.

---

## 🛠️ Technology Stack

### Frontend (JavaScript & JSX only)
- **Framework:** React 18, Vite
- **Language:** JavaScript & JSX (no TypeScript, `.jsx` / `.js` only)
- **Styling:** Tailwind CSS (deep observatory dark theme `#030712`, glassmorphic panels `backdrop-blur-md`)
- **Icons & Visuals:** Lucide React, Recharts (spectral plots)
- **Overlays:** SVG astronomical reticles, coordinate grid lines, and tracking vectors

### Backend (Python & FastAPI)
- **Framework:** FastAPI, Uvicorn (ASGI)
- **Astrometry & WCS:** `astropy` (FITS I/O, coordinates, WCS transformations, time)
- **Source Detection:** `photutils` (DAOStarFinder, aperture photometry, sigma-clipping)
- **Image Processing:** `numpy`, `scipy`, `matplotlib`, `pillow`
- **Virtual Observatory Access:** `pyvo`, `astroquery`, `httpx`
- **Testing:** `pytest`, `pytest-asyncio`

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.13)
- Node.js 18+ and npm

### 1. Start the Backend API
```bash
# In terminal 1:
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
```
Backend will be live at `http://localhost:8000` (OpenAPI Swagger docs: `http://localhost:8000/docs`).

### 2. Start the React Frontend
```bash
# In terminal 2:
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Automated Testing
Run the test suite verifying FITS HDU selection, WCS conversions, photutils source detection, and cross-epoch tracking:
```bash
# Run backend tests
PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v

# Run frontend build check
cd frontend && npm run build
```

---

## 🌌 Using Authentic SPHEREx Observations

1. **Load Demonstration:** Click **Load Demo** in the sidebar. A 3-epoch synthetic SPHEREx dataset loads instantly with clear `SIMULATED DEMO — NOT REAL SPHEREx DATA` indicators. Navigating the timeline scrubber demonstrates stationary stars remaining fixed while the moving body shifts across epochs.
2. **Load Authentic SPHEREx Data:** Click **Load Real SPHEREx** in the sidebar. The authentic 68.3 MB Level 2 calibrated spectral image from NASA IRSA (`2025W18_1B_0001_1_D1`) loads with genuine science coordinates (`CRVAL: [276.26°, 64.82°]`, scale: `6.16″/px`).
3. **Query the Archive:** Open **Search IRSA**, enter coordinates `RA: 276.0°`, `Dec: 65.0°`, and execute an ADQL search against `spherex.obscore`.
4. **Inspect & Track:** Click on any candidate source marker. The floating inspector displays its astrometric coordinates, peak brightness, SNR, cross-epoch matching status, LVF infrared SED plot, and kinematic prediction trajectory.

---

## 🚢 Production Deployment

### Backend on Render / Railway
1. Set **Root Directory** to `backend`.
2. Set **Build Command** to: `pip install -r requirements.txt`
3. Set **Start Command** to: `PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set environment variable: `MAX_UPLOAD_SIZE_BYTES=157286400`

### Frontend on Vercel
1. Set **Root Directory** to `frontend`.
2. Set **Framework Preset** to `Vite`.
3. Set environment variable: `VITE_BACKEND_URL=https://your-backend.onrender.com`
4. Deploy.

---

## 📄 License
This project is licensed under the MIT License. Developed for the 2026 NASA Space Apps Challenge (*Planet X and SPHEREx*).