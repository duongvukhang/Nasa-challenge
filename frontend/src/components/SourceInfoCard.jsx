import React, { useState } from "react";
import {
  Crosshair,
  X,
  Pin,
  PinOff,
  Activity,
  Compass,
  TrendingUp,
  Info,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";

export const SourceInfoCard = ({
  source,
  observation,
  onClose,
  onOpenSpectrum,
  onOpenPrediction,
  trackData = null
}) => {
  const [isPinned, setIsPinned] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  if (!source) return null;

  // Convert RA/Dec to sexagesimal string
  const formatRaDec = (ra, dec) => {
    if (ra == null || dec == null) return "No WCS Coordinates";
    const raH = Math.floor(ra / 15);
    const raM = Math.floor((ra / 15 - raH) * 60);
    const raS = ((ra / 15 - raH) * 60 - raM) * 60;

    const decSign = dec >= 0 ? "+" : "-";
    const absDec = Math.abs(dec);
    const decD = Math.floor(absDec);
    const decM = Math.floor((absDec - decD) * 60);
    const decS = ((absDec - decD) * 60 - decM) * 60;

    return `${raH}h ${raM}m ${raS.toFixed(1)}s, ${decSign}${decD}° ${decM}′ ${decS.toFixed(1)}″`;
  };

  // Find match status in trackData if available
  const currentEpochMatch = trackData?.timeline?.find(
    (ep) => ep.observation_id === observation?.observation_id
  );

  return (
    <div className="absolute top-16 right-3 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark rounded-2xl p-3.5 shadow-2xl border border-white/10 text-xs text-slate-300 w-72 sm:w-80 space-y-3">
        {/* Card Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Crosshair className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="font-bold text-white text-xs block">{source.id}</span>
              <span className="text-[10px] text-cyan-400 font-sans">SPHEREx Candidate Source</span>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            <button
              onClick={() => setIsPinned(!isPinned)}
              className={`p-1 rounded hover:bg-white/10 transition-colors ${
                isPinned ? "text-cyan-400" : "text-slate-400"
              }`}
              title={isPinned ? "Unpin Card" : "Pin Card"}
            >
              {isPinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
              title="Close Card"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Astrometric Coordinates */}
        <div className="space-y-1 bg-black/40 p-2.5 rounded-lg border border-white/5 text-[11px]">
          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">RA, Dec (deg):</span>
            <span className="text-white font-bold">
              {source.ra_deg != null ? `${source.ra_deg.toFixed(4)}°, ${source.dec_deg.toFixed(4)}°` : "N/A"}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">Sexagesimal:</span>
            <span className="text-slate-300 text-[10px]">
              {formatRaDec(source.ra_deg, source.dec_deg)}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">Pixel (X, Y):</span>
            <span className="text-slate-300">
              {source.pixel_x.toFixed(1)}, {source.pixel_y.toFixed(1)}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">Pos. Error (1σ):</span>
            <span className="text-cyan-400">
              ±{source.position_uncertainty_arcsec?.toFixed(3) || "0.300"}″
            </span>
          </div>
        </div>

        {/* Photometric Measurements */}
        <div className="space-y-1 bg-black/40 p-2.5 rounded-lg border border-white/5 text-[11px]">
          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">Peak Surface Flux:</span>
            <span className="text-cyan-300 font-bold">
              {source.peak_flux.toFixed(2)} {source.flux_unit}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">SNR:</span>
            <span className="text-white">{source.snr != null ? `${source.snr.toFixed(1)} σ` : "N/A"}</span>
          </div>

          <div className="flex justify-between">
            <span className="text-slate-400 font-sans">FWHM:</span>
            <span className="text-white">{source.fwhm_pixels?.toFixed(1) || "3.0"} px</span>
          </div>

          {trackData?.estimated_proper_motion_mas_yr != null && (
            <div className="flex justify-between border-t border-white/10 pt-1 mt-1">
              <span className="text-slate-400 font-sans">Apparent Motion:</span>
              <span className="text-cyan-400 font-bold">
                ~{trackData.estimated_proper_motion_mas_yr.toFixed(1)} mas/yr
              </span>
            </div>
          )}
        </div>

        {/* Quick Action Triggers */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            onClick={onOpenSpectrum}
            className="p-2 rounded-lg bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 transition-colors flex items-center justify-center space-x-1.5 text-[11px]"
          >
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>View Spectrum</span>
          </button>

          <button
            onClick={onOpenPrediction}
            className="p-2 rounded-lg bg-amber-950/50 hover:bg-amber-900/60 border border-amber-700/60 text-amber-200 transition-colors flex items-center justify-center space-x-1.5 text-[11px]"
          >
            <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
            <span>Predict Motion</span>
          </button>
        </div>
      </div>
    </div>
  );
};
