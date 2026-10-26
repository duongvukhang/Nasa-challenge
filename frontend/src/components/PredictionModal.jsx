import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  X,
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  Info
} from "lucide-react";
import { api } from "../services/api";

export const PredictionModal = ({
  isOpen,
  onClose,
  currentObservation,
  selectedSource,
  activeTrack = null,
  allObservations = [],
  onPredictionComputed
}) => {
  const [pmRa, setPmRa] = useState("0.0");
  const [pmDec, setPmDec] = useState("0.0");
  const [days, setDays] = useState("5.0");
  const [compObsId, setCompObsId] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Sync with active track motion if available when modal opens
  useEffect(() => {
    if (activeTrack?.fit_info?.rate_arcsec_day != null) {
      const rate = activeTrack.fit_info.rate_arcsec_day;
      const paDeg = activeTrack.fit_info.position_angle_deg || 0.0;
      const paRad = (paDeg * Math.PI) / 180.0;
      const vx = rate * Math.sin(paRad);
      const vy = rate * Math.cos(paRad);
      setPmRa(vx.toFixed(3));
      setPmDec(vy.toFixed(3));
    } else {
      setPmRa("0.0");
      setPmDec("0.0");
    }
  }, [isOpen, activeTrack]);

  if (!isOpen) return null;

  const handleCompute = async () => {
    if (!selectedSource || selectedSource.ra_deg == null || selectedSource.dec_deg == null) {
      setError("Please select a source with valid celestial coordinates.");
      return;
    }

    if (currentObservation?.mjd_obs == null) {
      setError("Active observation lacks a valid calibrated timestamp (MJD-OBS). Prediction requires a verified observation epoch.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await api.computePrediction({
        reference_observation_id: currentObservation.observation_id,
        target_ra_deg: selectedSource.ra_deg,
        target_dec_deg: selectedSource.dec_deg,
        target_time_mjd: currentObservation.mjd_obs,
        pm_ra_cosdec_arcsec_day: parseFloat(pmRa) || 0.0,
        pm_dec_arcsec_day: parseFloat(pmDec) || 0.0,
        extrapolation_days: parseFloat(days) || 5.0,
        comparison_observation_id: compObsId || undefined
      });
      setPrediction(res);
      if (onPredictionComputed) {
        onPredictionComputed(res);
      }
    } catch (err) {
      setError(err.message || "Failed to calculate prediction");
    } finally {
      setLoading(false);
    }
  };

  const otherObs = allObservations.filter(
    (o) => o.observation_id !== currentObservation?.observation_id
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 select-none font-mono">
      <div className="stellarium-glass-dark border border-white/10 w-full max-w-lg rounded-2xl shadow-2xl p-4 text-xs text-slate-300 space-y-3 max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <span className="font-bold text-white text-xs uppercase tracking-wider">
              Kinematic Motion Extrapolation & Verification
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Selected target info */}
        {selectedSource && (
          <div className="p-2 rounded bg-black/40 border border-white/5 flex justify-between text-[11px]">
            <span>Target: <strong className="text-white">{selectedSource.id}</strong></span>
            <span className="text-cyan-400 font-bold">
              RA {selectedSource.ra_deg?.toFixed(4)}°, Dec {selectedSource.dec_deg?.toFixed(4)}°
            </span>
          </div>
        )}

        {/* Motion Presets */}
        <div className="flex items-center space-x-2">
          <span className="text-[10px] text-slate-400 font-sans">Prior Presets:</span>
          {activeTrack?.fit_info?.rate_arcsec_day != null && (
            <button
              onClick={() => {
                const rate = activeTrack.fit_info.rate_arcsec_day;
                const paDeg = activeTrack.fit_info.position_angle_deg || 0.0;
                const paRad = (paDeg * Math.PI) / 180.0;
                setPmRa((rate * Math.sin(paRad)).toFixed(3));
                setPmDec((rate * Math.cos(paRad)).toFixed(3));
              }}
              className="px-2 py-0.5 rounded bg-cyan-950 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-200 text-[10px]"
            >
              Fitted Track ({activeTrack.fit_info.rate_arcsec_day.toFixed(2)}"/d)
            </button>
          )}
          <button
            onClick={() => { setPmRa("0.0"); setPmDec("0.0"); }}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 text-[10px]"
          >
            Static (0.0)
          </button>
          <button
            onClick={() => { setPmRa("0.5"); setPmDec("0.2"); }}
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-white/10 text-slate-200 text-[10px]"
          >
            Slow Mover (~0.5"/d)
          </button>
        </div>

        {/* Input parameters */}
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5 font-sans">μ_α* (arcsec/day)</label>
              <input
                type="number"
                step="0.1"
                value={pmRa}
                onChange={(e) => setPmRa(e.target.value)}
                className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5 font-sans">μ_δ (arcsec/day)</label>
              <input
                type="number"
                step="0.1"
                value={pmDec}
                onChange={(e) => setPmDec(e.target.value)}
                className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5 font-sans">Extrapolation Window (days)</label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="60"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5 font-sans">Verify Against Observation</label>
              <select
                value={compObsId}
                onChange={(e) => setCompObsId(e.target.value)}
                className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="">None (Model only)</option>
                {otherObs.map((o) => (
                  <option key={o.observation_id} value={o.observation_id}>
                    {o.filename.slice(0, 16)}... ({o.date_obs ? o.date_obs.slice(5, 10) : "epoch"})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleCompute}
            disabled={loading}
            className="w-full py-2 rounded-lg bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 font-bold text-white shadow-lg transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50 text-xs"
          >
            <PlayCircle className="w-4 h-4" />
            <span>{loading ? "Calculating..." : "Compute Extrapolation"}</span>
          </button>
        </div>

        {error && (
          <div className="p-2 rounded bg-rose-950/50 border border-rose-500/30 text-rose-300 text-[11px] flex items-center space-x-1.5">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Results */}
        {prediction && (
          <div className="space-y-2 border-t border-white/10 pt-2 text-[11px]">
            <div className="flex items-center justify-between text-amber-300 font-bold">
              <span>{prediction.model_type}</span>
              <span>{prediction.trajectory_points?.length || 0} Points</span>
            </div>

            {/* Verification result */}
            {prediction.verification && (
              <div
                className={`p-2.5 rounded-lg border font-mono ${
                  prediction.verification.is_consistent_with_model || prediction.verification.detected
                    ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-200"
                    : (prediction.verification.coverage_status === "outside_coverage" || prediction.verification.status === "outside_coverage")
                    ? "bg-slate-900/60 border-slate-700 text-slate-300"
                    : "bg-amber-950/40 border-amber-500/40 text-amber-200"
                }`}
              >
                <div className="flex items-center space-x-1.5 font-bold text-xs">
                  {(prediction.verification.is_consistent_with_model || prediction.verification.detected) ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  )}
                  <span>Coverage Status: {prediction.verification.coverage_status || prediction.verification.status}</span>
                </div>
                <div className="text-[10px] mt-1.5 space-y-1">
                  <div>Predicted: ({(prediction.verification.predicted_ra_deg ?? prediction.verification.predicted_ra)?.toFixed(4)}°, {(prediction.verification.predicted_dec_deg ?? prediction.verification.predicted_dec)?.toFixed(4)}°)</div>
                  {prediction.verification.observed_ra_deg != null && (
                    <div>Observed: ({prediction.verification.observed_ra_deg?.toFixed(4)}°, {prediction.verification.observed_dec_deg?.toFixed(4)}°)</div>
                  )}
                  {(prediction.verification.angular_residual_arcsec != null || prediction.verification.closest_source_separation_arcsec != null) && (
                    <div>
                      Separation: {(prediction.verification.angular_residual_arcsec ?? prediction.verification.closest_source_separation_arcsec)?.toFixed(2)}″
                      {prediction.verification.residual_sigma != null && ` (${prediction.verification.residual_sigma.toFixed(1)}σ)`}
                    </div>
                  )}
                  {prediction.verification.assessment && (
                    <div className="pt-1 text-slate-300 border-t border-white/5 font-sans leading-relaxed">
                      {prediction.verification.assessment}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Assumptions & Physical Limitations */}
            <div className="p-2 rounded bg-black/40 border border-white/5 space-y-1 text-[10px] text-slate-400">
              <div className="font-bold text-slate-300 flex items-center space-x-1">
                <Info className="w-3 h-3 text-cyan-400" />
                <span>Physical Assumptions & Limitations</span>
              </div>
              <ul className="list-disc pl-4 space-y-0.5">
                {prediction.limitations?.map((lim, i) => (
                  <li key={i}>{lim}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
