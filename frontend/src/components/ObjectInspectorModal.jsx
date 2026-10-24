import React, { useState } from "react";
import {
  X,
  Crosshair,
  Trash2,
  Maximize2,
  Activity,
  Compass,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Info,
  Layers,
  Sparkles,
  ExternalLink,
  ShieldAlert
} from "lucide-react";

export const ObjectInspectorModal = ({
  isOpen,
  onClose,
  source,
  observation,
  activeTrack,
  onDeleteSource,
  onCenterSource,
  onOpenSpectrum,
  onOpenPrediction,
  onTrackSource
}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (!isOpen || !source) return null;

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

    return {
      raStr: `${raH}h ${raM}m ${raS.toFixed(2)}s`,
      decStr: `${decSign}${decD}° ${decM}′ ${decS.toFixed(2)}″`
    };
  };

  const sexa = formatRaDec(source.ra_deg, source.dec_deg);
  const pixelScale = observation?.wcs?.pixel_scale_arcsec || 6.2;
  const fwhmArcsec = source.fwhm_pixels ? (source.fwhm_pixels * pixelScale).toFixed(2) : null;

  const handleDelete = () => {
    if (onDeleteSource) {
      onDeleteSource(source.id);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/75 backdrop-blur-sm pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark border border-white/15 rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        
        {/* Modal Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-black/40">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-400 border border-cyan-500/30">
              <Crosshair className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-white font-bold text-sm tracking-wide">{source.id}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-sans font-medium bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                  {source.is_tracked_target ? "Tracked Target" : "Detected Celestial Source"}
                </span>
                {activeTrack && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-sans font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    Track: {activeTrack.track_id}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 font-sans mt-0.5">
                Obs: <span className="text-slate-200">{observation?.observation_id || "Active Epoch"}</span> • {observation?.filename || ""}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-1.5">
            {onCenterSource && (
              <button
                onClick={() => onCenterSource(source)}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 transition-colors flex items-center space-x-1 text-xs"
                title="Center in Viewport"
              >
                <Maximize2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Center</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
              title="Close Inspector"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          
          {/* Section 1: Astrometric Coordinates */}
          <div className="bg-black/30 rounded-xl p-3.5 border border-white/10 space-y-2">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Astrometric Solution & Celestial Coordinates</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5 space-y-1">
                <span className="text-[10px] text-slate-400 font-sans block">Equatorial J2000 (Decimal Degrees)</span>
                <div className="text-white font-bold">
                  RA: <span className="text-cyan-300">{source.ra_deg != null ? `${source.ra_deg.toFixed(6)}°` : "N/A"}</span>
                </div>
                <div className="text-white font-bold">
                  Dec: <span className="text-cyan-300">{source.dec_deg != null ? `${source.dec_deg.toFixed(6)}°` : "N/A"}</span>
                </div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5 space-y-1">
                <span className="text-[10px] text-slate-400 font-sans block">Sexagesimal Coordinates (J2000)</span>
                <div className="text-slate-200 text-[11px]">
                  α: <span className="font-bold">{sexa.raStr}</span>
                </div>
                <div className="text-slate-200 text-[11px]">
                  δ: <span className="font-bold">{sexa.decStr}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1 text-[11px]">
              <div>
                <span className="text-slate-400 font-sans block">Focal-Plane Pixel:</span>
                <span className="text-white font-bold">
                  X: {source.pixel_x?.toFixed(2)}, Y: {source.pixel_y?.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 font-sans block">1σ Astrometric Error:</span>
                <span className="text-cyan-400 font-bold">
                  ±{source.position_uncertainty_arcsec?.toFixed(3) || "0.300"}″
                </span>
              </div>
              <div>
                <span className="text-slate-400 font-sans block">Plate Scale:</span>
                <span className="text-slate-300">
                  {pixelScale.toFixed(2)}″ / pixel
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Photometric Properties & Morphology */}
          <div className="bg-black/30 rounded-xl p-3.5 border border-white/10 space-y-2">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Activity className="w-3.5 h-3.5 text-amber-400" />
              <span>Photometry & Point Spread Function</span>
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <span className="text-[10px] text-slate-400 font-sans block">Peak Surface Flux</span>
                <span className="text-amber-300 font-bold text-sm">
                  {source.peak_flux != null ? source.peak_flux.toFixed(2) : "0.00"}
                </span>
                <span className="text-[10px] text-slate-400 block">{source.flux_unit || "MJy/sr"}</span>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <span className="text-[10px] text-slate-400 font-sans block">Detection SNR</span>
                <span className="text-white font-bold text-sm">
                  {source.snr != null ? `${source.snr.toFixed(1)} σ` : "N/A"}
                </span>
                <span className="text-[10px] text-emerald-400 block">
                  {source.snr && source.snr > 5 ? "High Confidence" : "Candidate"}
                </span>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <span className="text-[10px] text-slate-400 font-sans block">FWHM Core Width</span>
                <span className="text-white font-bold text-sm">
                  {source.fwhm_pixels?.toFixed(1) || "3.0"} px
                </span>
                <span className="text-[10px] text-slate-400 block">
                  {fwhmArcsec ? `~${fwhmArcsec}″ on sky` : ""}
                </span>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <span className="text-[10px] text-slate-400 font-sans block">Band / Channel</span>
                <span className="text-cyan-300 font-bold text-sm">
                  {observation?.band || "LVF"}
                </span>
                <span className="text-[10px] text-slate-400 block truncate">
                  SPHEREx Infrared
                </span>
              </div>
            </div>
          </div>

          {/* Section 3: Multi-Epoch Trajectory Status */}
          <div className="bg-black/30 rounded-xl p-3.5 border border-white/10 space-y-2">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>Multi-Epoch Trajectory Association</span>
            </h4>

            {activeTrack ? (
              <div className="bg-cyan-950/30 p-3 rounded-lg border border-cyan-500/30 flex items-center justify-between text-xs">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-white">{activeTrack.track_id}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300">
                      {activeTrack.quality_status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-sans mt-0.5">
                    Detected in {activeTrack.detected_epochs_count} of {activeTrack.total_eligible_epochs} loaded epochs
                  </p>
                </div>

                {activeTrack.fit_info?.proper_motion_mas_yr != null && (
                  <div className="text-right">
                    <span className="text-cyan-300 font-bold block">
                      ~{activeTrack.fit_info.proper_motion_mas_yr.toFixed(1)} mas/yr
                    </span>
                    <span className="text-[10px] text-slate-400">
                      PA: {activeTrack.fit_info.position_angle_deg?.toFixed(1) || 0}°
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-between text-xs p-2.5 bg-white/5 rounded-lg border border-white/5">
                <span className="text-slate-400 font-sans">
                  No multi-epoch trajectory calculated for this object yet.
                </span>
                {onTrackSource && (
                  <button
                    onClick={() => onTrackSource(source)}
                    className="px-2.5 py-1 rounded-md bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-300 transition-colors text-xs font-sans font-medium"
                  >
                    Track Across Epochs →
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Section 4: Object Management & Actions */}
          <div className="bg-black/30 rounded-xl p-3.5 border border-white/10 space-y-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Scientific Tools & Management</span>
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {onOpenSpectrum && (
                <button
                  onClick={onOpenSpectrum}
                  className="p-2.5 rounded-lg bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 transition-colors flex items-center space-x-2"
                >
                  <Activity className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  <div className="text-left font-sans">
                    <span className="font-bold block">View Infrared Spectrum</span>
                    <span className="text-[10px] text-slate-400">Extract 96-band spectral energy</span>
                  </div>
                </button>
              )}

              {onOpenPrediction && (
                <button
                  onClick={onOpenPrediction}
                  className="p-2.5 rounded-lg bg-amber-950/50 hover:bg-amber-900/60 border border-amber-700/60 text-amber-200 transition-colors flex items-center space-x-2"
                >
                  <TrendingUp className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <div className="text-left font-sans">
                    <span className="font-bold block">Predict Motion</span>
                    <span className="text-[10px] text-slate-400">Extrapolate future celestial track</span>
                  </div>
                </button>
              )}
            </div>

            {/* Danger Zone: Delete / Remove Source */}
            <div className="border-t border-white/10 pt-3">
              {!confirmDelete ? (
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-rose-300 block">Delete Object from Catalog</span>
                    <span className="text-[11px] text-slate-400 font-sans">
                      Removes this source from detections and detaches active trajectory track.
                    </span>
                  </div>
                  <button
                    onClick={() => setConfirmDelete(true)}
                    className="px-3 py-1.5 rounded-lg bg-red-950/70 hover:bg-red-900 border border-red-700/60 text-red-200 transition-colors flex items-center space-x-1.5 text-xs font-sans font-bold flex-shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete Object</span>
                  </button>
                </div>
              ) : (
                <div className="bg-red-950/60 p-3 rounded-xl border border-red-500/50 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2 text-red-200 text-xs">
                    <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
                    <span>Are you sure you want to delete <strong>{source.id}</strong>?</span>
                  </div>
                  <div className="flex items-center space-x-2 font-sans text-xs">
                    <button
                      onClick={() => setConfirmDelete(false)}
                      className="px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDelete}
                      className="px-3 py-1 rounded-md bg-red-600 hover:bg-red-500 text-white font-bold transition-colors shadow-lg"
                    >
                      Confirm Delete
                    </button>
                  </div>
                </div>
              )}
            </div>

          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-white/10 bg-black/50 flex items-center justify-between text-xs font-sans text-slate-400">
          <span>SPHEREx Astrometric Target Management</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
