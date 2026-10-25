import React, { useState } from "react";
import {
  X,
  XCircle,
  Compass,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  AlertCircle,
  Activity,
  Maximize2,
  Trash2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  Sparkles,
  Download,
  RotateCcw,
  RotateCw
} from "lucide-react";
import { api } from "../services/api";
import { getStableTrackColor } from "../utils/colors";

export const TrajectoryInspector = ({
  isOpen,
  onClose,
  track,
  onOpenSkyPlot,
  onFocusTrack,
  onDeleteTrack,
  onSelectObservation,
  onUpdateTrack = null,
  onStopInspect = null
}) => {
  const [activeTab, setActiveTab] = useState("timeline"); // "timeline" | "fit" | "missed"

  if (!isOpen || !track) return null;

  const trackColor = track.color || getStableTrackColor(track.track_id);
  const fit = track.fit_info || {};
  const validation = track.validation_info || {};
  const timeline = track.timeline || [];

  // Status badge helper
  const renderStatusBadge = (status) => {
    switch (status) {
      case "STRONG MATCH":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>STRONG MATCH</span>
          </span>
        );
      case "REVIEW NEEDED":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>REVIEW NEEDED</span>
          </span>
        );
      case "AMBIGUOUS":
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>AMBIGUOUS</span>
          </span>
        );
      case "INSUFFICIENT DATA":
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-500/20 text-slate-300 border border-slate-500/40">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>INSUFFICIENT DATA</span>
          </span>
        );
    }
  };

  const missedEpochs = timeline.filter((ep) => !ep.is_measured);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/70 backdrop-blur-sm pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark border border-white/15 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        
        {/* Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-black/40">
          <div className="flex items-center space-x-3">
            <div
              className="w-4 h-4 rounded-full shadow-lg"
              style={{ backgroundColor: trackColor, boxShadow: `0 0 10px ${trackColor}` }}
              title={`Track Color: ${trackColor}`}
            />
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-white font-bold text-sm tracking-wide">{track.display_name || track.track_id}</span>
                {track.display_name && track.display_name !== track.track_id && (
                  <span className="text-[11px] text-slate-400 font-sans">({track.track_id})</span>
                )}
                {renderStatusBadge(track.quality_status)}
                <span className="text-xs text-slate-400 font-sans">
                  Ref: <span className="text-cyan-300">{track.reference_source_id}</span> ({track.reference_observation_id})
                </span>
              </div>
              <p className="text-[11px] text-slate-300 font-sans mt-0.5 line-clamp-1">
                {track.quality_rationale}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* Undo / Redo */}
            <button
              onClick={async () => {
                try {
                  const undone = await api.undoTrack(track.track_id);
                  if (onUpdateTrack) onUpdateTrack(undone);
                } catch (e) {
                  alert(e.message);
                }
              }}
              disabled={!track.history || track.history.length <= 1}
              className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-300 disabled:opacity-30 transition-colors"
              title="Undo last modification"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={async () => {
                try {
                  const redone = await api.redoTrack(track.track_id);
                  if (onUpdateTrack) onUpdateTrack(redone);
                } catch (e) {
                  alert(e.message);
                }
              }}
              disabled={!track.redo_stack || track.redo_stack.length === 0}
              className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-300 disabled:opacity-30 transition-colors"
              title="Redo last modification"
            >
              <RotateCw className="w-3.5 h-3.5" />
            </button>

            {/* Export Dropdown / Buttons */}
            <a
              href={api.getTrackExportUrl(track.track_id, "csv")}
              download={`${track.track_id}.csv`}
              className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 transition-colors flex items-center space-x-1 text-xs"
              title="Export verifiable track table as CSV"
            >
              <Download className="w-3 h-3 text-cyan-400" />
              <span>CSV</span>
            </a>
            <a
              href={api.getTrackExportUrl(track.track_id, "json")}
              download={`${track.track_id}.json`}
              className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 transition-colors flex items-center space-x-1 text-xs"
              title="Export complete provenance and astrometry as JSON"
            >
              <Download className="w-3 h-3 text-cyan-400" />
              <span>JSON</span>
            </a>

            <button
              onClick={() => onOpenSkyPlot?.(track)}
              className="px-2.5 py-1 rounded-lg bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 transition-colors flex items-center space-x-1.5 text-xs"
              title="Open Historical Sky-Coordinate Plot"
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Sky Plot</span>
            </button>
            <button
              onClick={() => onFocusTrack?.(track)}
              className="px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-white/10 text-slate-200 transition-colors flex items-center space-x-1.5 text-xs"
              title="Focus in viewer"
            >
              <Maximize2 className="w-3.5 h-3.5 text-slate-300" />
              <span>Focus</span>
            </button>
            {onStopInspect && (
              <button
                onClick={() => {
                  onStopInspect(track.track_id);
                  onClose();
                }}
                className="px-2.5 py-1 rounded-lg bg-rose-950/70 hover:bg-rose-900 border border-rose-500/50 text-rose-200 transition-colors flex items-center space-x-1.5 text-xs font-bold"
                title="Remove trajectory and dots from viewer"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                <span>Remove Trajectory</span>
              </button>
            )}
            {onDeleteTrack && (
              <button
                onClick={() => {
                  if (confirm(`Delete track ${track.track_id}?`)) {
                    onDeleteTrack(track.track_id);
                    onClose();
                  }
                }}
                className="p-1 rounded-lg hover:bg-red-950/60 text-slate-400 hover:text-red-300 transition-colors border border-transparent hover:border-red-500/30"
                title="Delete track"
              >
                <Trash2 className="w-4 h-4" />
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

        {/* Metric Summary Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-black/30 border-b border-white/10 text-xs">
          <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
            <span className="text-[10px] text-slate-400 font-sans block">Detection Completeness</span>
            <span className="text-white font-bold text-sm">
              {track.detected_epochs_count} / {track.total_eligible_epochs}{" "}
              <span className="text-slate-400 text-xs font-normal">epochs</span>
            </span>
            <span className="text-[10px] text-cyan-400 block mt-0.5">
              {track.missed_epochs_count > 0 ? `${track.missed_epochs_count} missed/outside FOV` : "100% Detected"}
            </span>
          </div>

          <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
            <span className="text-[10px] text-slate-400 font-sans block">Trajectory Model</span>
            <span className="text-cyan-300 font-bold text-xs truncate block" title={fit.fit_model}>
              {fit.fit_model || "None"}
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              {fit.is_verified_motion ? "✓ Verified Kinematics" : "Unverified / Stationary"}
            </span>
          </div>

          <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
            <span className="text-[10px] text-slate-400 font-sans block">Apparent Velocity & PA</span>
            <span className="text-white font-bold text-xs block">
              {fit.proper_motion_mas_yr != null
                ? `${fit.proper_motion_mas_yr.toFixed(1)} ± ${fit.proper_motion_uncertainty_mas_yr?.toFixed(1) || 0} mas/yr`
                : "N/A (Stationary)"}
            </span>
            <span className="text-[10px] text-slate-400 block mt-0.5">
              {fit.rate_arcsec_day != null ? `${fit.rate_arcsec_day.toFixed(3)}″/d (${(fit.rate_arcsec_day / 24).toFixed(4)}″/h)` : `PA: ${fit.position_angle_deg != null ? `${fit.position_angle_deg.toFixed(1)}°` : "—"}`}
            </span>
          </div>

          <div className="bg-white/5 rounded-xl p-2.5 border border-white/5">
            <span className="text-[10px] text-slate-400 font-sans block">Fit Goodness & RMS</span>
            <span className="text-white font-bold text-xs block">
              RMS: {fit.rms_residual_arcsec != null ? `${fit.rms_residual_arcsec.toFixed(3)}″` : "0.000″"}
            </span>
            <span className="text-[10px] text-amber-300 block mt-0.5">
              χ²_red: {fit.reduced_chi2 != null ? fit.reduced_chi2.toFixed(2) : "—"} (DoF: {fit.degrees_of_freedom ?? "0"})
            </span>
          </div>
        </div>

        {/* Scientific Integrity Disclaimer Banner */}
        <div className="px-4 py-2 bg-amber-950/30 border-b border-amber-500/20 text-[10px] text-amber-300/90 flex items-center justify-between">
          <div className="flex items-center space-x-1.5">
            <Info className="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <span>{fit.disclaimer || "Statistical motion candidate does not establish orbit determination or celestial body identification."}</span>
          </div>
          {fit.velocity_significance_sigma != null && (
            <span className="px-1.5 py-0.5 rounded bg-black/40 text-amber-200 border border-amber-500/30">
              Significance: {fit.velocity_significance_sigma.toFixed(1)}σ
            </span>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-white/10 px-4 bg-black/20 text-xs font-sans">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`py-2 px-3 border-b-2 font-medium transition-colors ${
              activeTab === "timeline"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Detection Timeline ({timeline.length})
          </button>
          <button
            onClick={() => setActiveTab("fit")}
            className={`py-2 px-3 border-b-2 font-medium transition-colors ${
              activeTab === "fit"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Scientific Fit & Validation
          </button>
          <button
            onClick={() => setActiveTab("missed")}
            className={`py-2 px-3 border-b-2 font-medium transition-colors ${
              activeTab === "missed"
                ? "border-cyan-400 text-cyan-300"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            Missed Epochs ({missedEpochs.length})
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          
          {/* TAB 1: Timeline Table */}
          {activeTab === "timeline" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-sans text-[11px]">
                    <th className="py-2 px-2">Epoch / Band</th>
                    <th className="py-2 px-2">Observation Date & MJD</th>
                    <th className="py-2 px-2">Measured RA, Dec (J2000)</th>
                    <th className="py-2 px-2">Pixel (X, Y)</th>
                    <th className="py-2 px-2">Status</th>
                    <th className="py-2 px-2 text-right">Sep (″)</th>
                    <th className="py-2 px-2 text-right">Residual (″ / σ)</th>
                    <th className="py-2 px-2 text-right">SNR / Flux</th>
                    <th className="py-2 px-2 text-center">Cand</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {timeline.map((ep, idx) => {
                    const isRef = ep.observation_id === track.reference_observation_id;
                    return (
                      <React.Fragment key={ep.observation_id || idx}>
                        <tr
                          onClick={() => onSelectObservation?.(ep.observation_id)}
                          className={`hover:bg-white/5 transition-colors cursor-pointer ${
                            isRef ? "bg-cyan-950/20" : ""
                          }`}
                        >
                        <td className="py-2 px-2 whitespace-nowrap">
                          <div className="flex items-center space-x-1.5">
                            <span className="font-bold text-white">E{idx + 1}</span>
                            {isRef && (
                              <span className="px-1 rounded bg-cyan-500/20 text-cyan-300 text-[10px]">
                                REF
                              </span>
                            )}
                            <span className="text-slate-400 text-[11px] font-sans">
                              {ep.band || "LVF"}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 block truncate max-w-[120px]">
                            {ep.observation_id}
                          </span>
                          {ep.matched_source_id && (
                            <span className="text-[10px] text-cyan-400 font-mono block truncate max-w-[140px]" title={`Detection ID: ${ep.matched_source_id}`}>
                              {ep.matched_source_id}
                            </span>
                          )}
                        </td>

                        <td className="py-2 px-2 whitespace-nowrap">
                          <span className="text-slate-200 block text-[11px]">
                            {ep.date_obs ? ep.date_obs.replace("T", " ").slice(0, 19) : "N/A"}
                          </span>
                          <span className="text-slate-500 text-[10px]">
                            MJD {ep.mjd_obs != null ? ep.mjd_obs.toFixed(4) : "—"}
                          </span>
                        </td>

                        <td className="py-2 px-2 whitespace-nowrap">
                          {ep.is_measured ? (
                            <>
                              <span className="text-white block">
                                {ep.ra_deg?.toFixed(5)}°, {ep.dec_deg?.toFixed(5)}°
                              </span>
                              <span className="text-cyan-400 text-[10px]">
                                ±{ep.position_uncertainty_arcsec?.toFixed(3) || "0.300"}″
                              </span>
                            </>
                          ) : (
                            <span className="text-slate-500 italic">Not measured</span>
                          )}
                        </td>

                        <td className="py-2 px-2 whitespace-nowrap">
                          {ep.pixel_x != null && ep.pixel_y != null ? (
                            <span className="text-slate-300">
                              {ep.pixel_x.toFixed(1)}, {ep.pixel_y.toFixed(1)}
                            </span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="py-2 px-2 whitespace-nowrap">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                              ep.status === "Likely match"
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : ep.status === "Ambiguous match"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                : ep.status === "Outside FOV"
                                ? "bg-slate-700/40 text-slate-400"
                                : "bg-amber-500/20 text-amber-300"
                            }`}
                          >
                            {ep.status}
                          </span>
                          {ep.is_measured ? (
                            <span className="ml-1 text-[9px] text-emerald-400 font-sans">
                              ● MEASURED
                            </span>
                          ) : (
                            <span className="ml-1 text-[9px] text-slate-500 font-sans">
                              ○ NO DETECTION
                            </span>
                          )}
                        </td>

                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {ep.separation_arcsec != null ? (
                            <>
                              <span className="text-slate-200 block">
                                {ep.separation_arcsec.toFixed(2)}″
                              </span>
                              <span className="text-slate-500 text-[10px]">
                                {ep.separation_sigma != null ? `${ep.separation_sigma.toFixed(1)}σ` : ""}
                              </span>
                            </>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {ep.residual_arcsec != null ? (
                            <>
                              <span className="text-amber-300 block">
                                {ep.residual_arcsec.toFixed(2)}″
                              </span>
                              <span className="text-slate-500 text-[10px]">
                                {ep.residual_sigma != null ? `${ep.residual_sigma.toFixed(1)}σ` : ""}
                              </span>
                            </>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="py-2 px-2 text-right whitespace-nowrap">
                          {ep.snr != null ? (
                            <>
                              <span className="text-white block">{ep.snr.toFixed(1)} σ</span>
                              <span className="text-slate-400 text-[10px]">
                                {ep.flux != null ? `${ep.flux.toFixed(1)} ${ep.flux_unit || ""}` : ""}
                              </span>
                            </>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="py-2 px-2 text-center whitespace-nowrap">
                          <span
                            className={`px-1 rounded text-[10px] ${
                              ep.candidate_count > 1 ? "bg-rose-500/30 text-rose-200" : "text-slate-400"
                            }`}
                          >
                            {ep.candidate_count}
                          </span>
                        </td>
                      </tr>
                      {ep.competing_candidates && ep.status === "Ambiguous match" && (
                        <tr key={`comp_${ep.observation_id}`} className="bg-rose-950/20 text-[10px]">
                          <td colSpan={9} className="py-2 px-3">
                            <div className="font-bold text-rose-300 mb-1 flex items-center space-x-1">
                              <AlertCircle className="w-3 h-3 text-rose-400" />
                              <span>Competing Candidates ({ep.competing_candidates.length}):</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {ep.competing_candidates.map((cand) => (
                                <div key={cand.source_id} className="p-1.5 rounded bg-black/60 border border-white/10 flex items-center space-x-2">
                                  <span className="font-bold text-white">{cand.source_id}</span>
                                  <span className="text-slate-400">Sep: {cand.separation_arcsec}″</span>
                                  <span className="text-slate-400">SNR: {cand.snr?.toFixed(1) || "—"}σ</span>
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      try {
                                        const updated = await api.acceptCandidate(track.track_id, ep.observation_id, cand.source_id);
                                        if (onUpdateTrack) onUpdateTrack(updated);
                                      } catch (err) {
                                        alert(err.message);
                                      }
                                    }}
                                    className="px-2 py-0.5 rounded bg-cyan-700 hover:bg-cyan-600 text-white font-sans text-[10px] shadow"
                                  >
                                    Accept
                                  </button>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 2: Scientific Fit & Validation */}
          {activeTab === "fit" && (
            <div className="space-y-4">
              <div className="bg-black/40 rounded-xl p-3.5 border border-white/10 space-y-2">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
                  <Activity className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Trajectory Fit Assessment</span>
                </h4>
                <p className="text-slate-300 text-xs leading-relaxed font-sans">
                  {fit.fit_assessment || "No fit assessment available."}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 text-xs">
                  <div>
                    <span className="text-slate-500 text-[11px] block">Model Type:</span>
                    <span className="text-cyan-300 font-bold">{fit.fit_model}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px] block">Kinematic Verification:</span>
                    <span className={fit.is_verified_motion ? "text-emerald-400 font-bold" : "text-slate-400 font-bold"}>
                      {fit.is_verified_motion ? "Verified (N ≥ 3)" : "Not verified as motion"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px] block">Max Residual Sigma:</span>
                    <span className="text-white font-bold">
                      {fit.max_residual_sigma != null ? `${fit.max_residual_sigma.toFixed(2)} σ` : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-black/40 rounded-xl p-3.5 border border-white/10 space-y-2">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center space-x-2">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Catalog & Astrometric Validation</span>
                </h4>
                <div className="space-y-1.5 text-xs font-sans">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Reference Catalog / Service:</span>
                    <span className="text-slate-200 font-mono">{validation.reference_catalog_or_service || "SPHEREx Internal Astrometry"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Validation Status:</span>
                    <span className="text-cyan-300 font-mono">{validation.validation_status || "Unvalidated"}</span>
                  </div>
                  {validation.validation_details && (
                    <div className="pt-2 text-slate-400 text-[11px]">
                      {validation.validation_details}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Missed Epochs Breakdown */}
          {activeTab === "missed" && (
            <div className="space-y-3">
              {missedEpochs.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-xs font-sans">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
                  <span>All {track.total_eligible_epochs} eligible observation epochs have confirmed detections.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-slate-400 text-xs font-sans">
                    Truth-based tracking preserves real absence of detections without fabricating positions or synthetic markers:
                  </p>
                  {missedEpochs.map((ep, idx) => (
                    <div
                      key={ep.observation_id || idx}
                      className="bg-black/40 p-3 rounded-xl border border-white/5 flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="text-white font-bold block">{ep.observation_id}</span>
                        <span className="text-slate-400 text-[11px] font-sans">
                          {ep.date_obs ? ep.date_obs.slice(0, 19) : "Date unknown"} • Band {ep.band || "LVF"}
                        </span>
                      </div>
                      <div className="text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-bold ${
                            ep.status === "Outside FOV"
                              ? "bg-slate-700 text-slate-300"
                              : "bg-amber-950/80 text-amber-300 border border-amber-600/50"
                          }`}
                        >
                          {ep.status}
                        </span>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-sans">
                          {ep.confidence_rationale || "No candidate source detected"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-3 border-t border-white/10 bg-black/50 flex items-center justify-between text-xs">
          <div className="text-[11px] text-slate-400 font-sans">
            Created: {track.created_at ? new Date(track.created_at).toLocaleTimeString() : "Current session"}
          </div>
          <div className="flex items-center space-x-2">
            {onStopInspect && (
              <button
                onClick={() => {
                  onStopInspect(track.track_id);
                  onClose();
                }}
                className="px-3 py-1.5 rounded-lg bg-rose-950/70 hover:bg-rose-900 border border-rose-500/50 text-rose-200 font-sans text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                title="Remove trajectory and dots from viewer"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                <span>Remove Trajectory & Dots</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-sans text-xs transition-colors"
            >
              Close
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
