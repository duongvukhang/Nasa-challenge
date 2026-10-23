import React from "react";
import {
  X,
  BookOpen,
  Telescope,
  ShieldAlert,
  Compass,
  Activity,
  CheckCircle2
} from "lucide-react";

export const HowItWorksDialog = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none">
      <div className="stellarium-glass-dark border border-white/10 w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden text-xs text-slate-300">
        {/* Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-white">
            <BookOpen className="w-5 h-5 text-cyan-400" />
            <h3 className="font-bold text-sm tracking-wide uppercase">
              SkyTrace Scientific Methodology & Planet X Guidance
            </h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 overflow-y-auto leading-relaxed text-slate-300">
          <div>
            <h4 className="text-cyan-400 font-semibold text-xs uppercase tracking-wider mb-1 flex items-center space-x-1.5">
              <Telescope className="w-4 h-4" />
              <span>1. SPHEREx All-Sky Infrared Survey</span>
            </h4>
            <p className="text-slate-400">
              NASA’s <strong>SPHEREx</strong> mission maps the sky in 102 infrared wavelength channels (0.75 to 5.0 µm) using 6 Linear Variable Filters (LVF). In each calibrated FITS image, the observed wavelength varies continuously along the focal plane dispersion axis at ~6.2 arcseconds per pixel.
            </p>
          </div>

          <div className="bg-black/40 p-3 rounded-xl border border-white/5 space-y-2">
            <h5 className="font-bold text-white text-[11px] uppercase tracking-wider">
              Scientific Exploration Pipeline
            </h5>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[10px] text-center">
              <div className="p-2 rounded-lg bg-black/50 border border-white/5">
                <span className="text-cyan-400 font-bold block">1. Explore</span>
                <span className="text-slate-400">Inspect FITS arrays & WCS coords</span>
              </div>
              <div className="p-2 rounded-lg bg-black/50 border border-white/5">
                <span className="text-cyan-400 font-bold block">2. Detect</span>
                <span className="text-slate-400">DAOStarFinder PSF point sources</span>
              </div>
              <div className="p-2 rounded-lg bg-black/50 border border-white/5">
                <span className="text-cyan-400 font-bold block">3. Track</span>
                <span className="text-slate-400">Cross-epoch astrometric matching</span>
              </div>
              <div className="p-2 rounded-lg bg-black/50 border border-white/5">
                <span className="text-cyan-400 font-bold block">4. Verify</span>
                <span className="text-slate-400">LVF spectra & trajectory validation</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-cyan-400 font-semibold text-xs uppercase tracking-wider mb-2 flex items-center space-x-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>2. Essential Scientific Distinctions</span>
            </h4>
            <div className="space-y-2 text-[11px]">
              <div className="p-2 rounded-lg bg-black/40 border border-white/5">
                <strong className="text-white">Observation vs. Prediction:</strong> Real observations reflect genuine photons measured by SPHEREx. Predicted positions are kinematic angular extrapolations rendered with dashed lines and expanding error bounds.
              </div>
              <div className="p-2 rounded-lg bg-black/40 border border-white/5">
                <strong className="text-white">Real Data vs. Simulated Demo:</strong> Real observations originate from NASA/IPAC IRSA. Synthetic demo datasets are marked with amber beacons.
              </div>
              <div className="p-2 rounded-lg bg-black/40 border border-white/5">
                <strong className="text-white">Source Detection vs. Identification:</strong> A detection indicates an intensity enhancement above background noise ($N\sigma$). It does not claim that an object is a planet or asteroid. Background fluctuations and instrument artifacts can also produce candidate detections.
              </div>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-800/40 text-amber-200/90 space-y-1">
            <span className="font-bold flex items-center space-x-1">
              <span>Scientific Integrity & Planet X</span>
            </span>
            <p className="text-[11px] text-amber-300/80 leading-relaxed">
              SkyTrace does not claim to discover Planet X. A detected motion across two epochs can arise from high-proper-motion stars, solar system asteroids, or centroid jitter. Genuine physical identification requires multi-observatory orbital solutions and reflex parallax determination.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-white/10 bg-black/40 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>2026 NASA Space Apps Challenge</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-white transition-colors"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
};
