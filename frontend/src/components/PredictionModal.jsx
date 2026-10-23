import React, { useState } from "react";
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
  allObservations = [],
  onPredictionComputed
}) => {
  const [pmRa, setPmRa] = useState("1.5");
  const [pmDec, setPmDec] = useState("0.5");
  const [days, setDays] = useState("5.0");
  const [compObsId, setCompObsId] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleCompute = async () => {
    if (!selectedSource || selectedSource.ra_deg == null || selectedSource.dec_deg == null) {
      setError("Please select a source with valid celestial coordinates.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await api.computePrediction({
        reference_observation_id: currentObservation.observation_id,
        target_ra_deg: selectedSource.ra_deg,
        target_dec_deg: selectedSource.dec_deg,
        target_time_mjd: currentObservation.mjd_obs || 60793.0,
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
        </div>

        {error && <div className="p-2 rounded bg-red-950/40 border border-red-800 text-red-300 text-[10px]">{error}</div>}

        <button
          onClick={handleCompute}
          disabled={loading || !selectedSource}
          className="w-full py-2 rounded-lg bg-amber-950/60 hover:bg-amber-900 border border-amber-700/60 text-amber-200 transition-colors flex items-center justify-center space-x-1.5 font-bold disabled:opacity-40"
        >
          <PlayCircle className="w-4 h-4 text-amber-400" />
          <span>{loading ? "Computing Extrapolation..." : "Compute Predicted Trajectory"}</span>
        </button>

        {/* Verification Result */}
        {prediction?.verification && (
          <div className="p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-800/50 space-y-1 text-[11px]">
            <div className="flex items-center space-x-1.5 text-cyan-400 font-bold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Observation Verification</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-[10px]">
              <div>Residual: <strong className="text-white">{prediction.verification.angular_residual_arcsec.toFixed(2)}″</strong></div>
              <div>Deviation: <strong className={prediction.verification.is_consistent_with_model ? "text-cyan-400" : "text-amber-400"}>{prediction.verification.residual_sigma.toFixed(1)} σ</strong></div>
            </div>
            <p className="text-[10px] text-slate-400 font-sans">{prediction.verification.assessment}</p>
          </div>
        )}

        {/* Physical Limitations */}
        <div className="p-2.5 rounded-lg bg-black/40 border border-white/5 text-[10px] text-slate-400 font-sans space-y-1">
          <span className="text-amber-400 font-bold block">Scientific Assumptions:</span>
          <p>Kinematic extrapolation assumes constant sky velocity over short baselines. Real trans-Neptunian bodies exhibit curved orbital arcs and substantial Earth reflex parallax.</p>
        </div>
      </div>
    </div>
  );
};
