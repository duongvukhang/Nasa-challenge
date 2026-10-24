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
  AlertTriangle,
  Loader2,
  Search,
  Trash2,
  Maximize2
} from "lucide-react";

export const SourceInfoCard = ({
  source,
  observation,
  onClose,
  onOpenSpectrum,
  onOpenPrediction,
  trackData = null,
  activeTrack = null,
  onTrackSource = null,
  onInspectTrack = null,
  onOpenSkyPlot = null,
  isTrackingLoading = false,
  onInspectSource = null,
  onDeleteSource = null,
  onCenterSource = null
}) => {
  const [isPinned, setIsPinned] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);

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
            {onInspectSource && (
              <button
                onClick={() => onInspectSource(source)}
                className="p-1 rounded hover:bg-white/10 text-cyan-400 hover:text-cyan-200 transition-colors"
                title="Inspect Object Details"
              >
                <Search className="w-3.5 h-3.5" />
              </button>
            )}
            {onDeleteSource && (
              <button
                onClick={() => setShowConfirmDelete(true)}
                className="p-1 rounded hover:bg-red-950/60 text-slate-400 hover:text-red-300 transition-colors"
                title="Delete Object"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
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

        {/* Delete Confirmation Alert if triggered */}
        {showConfirmDelete && (
          <div className="bg-red-950/80 p-2.5 rounded-lg border border-red-500/50 flex items-center justify-between text-[11px] font-sans text-red-200">
            <span>Delete {source.id}?</span>
            <div className="flex items-center space-x-1.5">
              <button
                onClick={() => {
                  onDeleteSource(source.id);
                  setShowConfirmDelete(false);
                }}
                className="px-2 py-0.5 rounded bg-red-600 hover:bg-red-500 text-white font-bold"
              >
                Delete
              </button>
              <button
                onClick={() => setShowConfirmDelete(false)}
                className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

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

        {/* Multi-Epoch Trajectory Action / Status */}
        {activeTrack ? (
          <div className="bg-cyan-950/40 p-2.5 rounded-lg border border-cyan-500/30 space-y-2 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white flex items-center space-x-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block"
                  style={{ backgroundColor: activeTrack.color || "#22d3ee" }}
                />
                <span>{activeTrack.track_id}</span>
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                  activeTrack.quality_status === "STRONG MATCH"
                    ? "bg-emerald-500/20 text-emerald-300"
                    : activeTrack.quality_status === "REVIEW NEEDED"
                    ? "bg-amber-500/20 text-amber-300"
                    : "bg-rose-500/20 text-rose-300"
                }`}
              >
                {activeTrack.quality_status}
              </span>
            </div>

            <div className="flex items-center space-x-2 pt-1">
              <button
                onClick={() => onInspectTrack?.(activeTrack)}
                className="flex-1 py-1.5 px-2 rounded-md bg-cyan-900/60 hover:bg-cyan-800 border border-cyan-500/40 text-cyan-200 transition-colors flex items-center justify-center space-x-1 text-[11px]"
              >
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                <span>Inspect Quality</span>
              </button>
              <button
                onClick={() => onOpenSkyPlot?.(activeTrack)}
                className="py-1.5 px-2 rounded-md bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 transition-colors flex items-center justify-center text-[11px]"
                title="View Sky-Coordinate Plot"
              >
                <span>Sky Plot</span>
              </button>
            </div>
          </div>
        ) : onTrackSource ? (
          <button
            onClick={() => onTrackSource(source)}
            disabled={isTrackingLoading}
            className="w-full py-2 px-3 rounded-lg bg-gradient-to-r from-cyan-950 to-blue-950 hover:from-cyan-900 hover:to-blue-900 border border-cyan-500/50 text-cyan-200 transition-all flex items-center justify-center space-x-2 text-xs font-sans font-bold shadow-cyan-glow/20 disabled:opacity-50"
          >
            {isTrackingLoading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                <span>Tracking Across Epochs...</span>
              </>
            ) : (
              <>
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                <span>Track Across Epochs</span>
              </>
            )}
          </button>
        ) : null}

        {/* Quick Action Triggers */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          {onInspectSource && (
            <button
              onClick={() => onInspectSource(source)}
              className="p-2 rounded-lg bg-cyan-950/90 hover:bg-cyan-900 border border-cyan-500/50 text-cyan-200 transition-colors flex items-center justify-center space-x-1.5 text-[11px] shadow-cyan-glow/20"
            >
              <Search className="w-3.5 h-3.5 text-cyan-400" />
              <span>Inspect Object</span>
            </button>
          )}

          {onCenterSource && (
            <button
              onClick={() => onCenterSource(source)}
              className="p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-white/10 text-slate-200 transition-colors flex items-center justify-center space-x-1.5 text-[11px]"
            >
              <Maximize2 className="w-3.5 h-3.5 text-slate-300" />
              <span>Center View</span>
            </button>
          )}

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
