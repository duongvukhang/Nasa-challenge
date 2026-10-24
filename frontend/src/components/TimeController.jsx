import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Clock,
  Calendar,
  AlertCircle,
  Database
} from "lucide-react";

export const TimeController = ({
  observations = [],
  activeObservationId,
  onSelectObservation,
  isVisible = true
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1.0); // seconds per epoch
  const timerRef = useRef(null);

  // Chronologically sorted observations by MJD
  const sortedObs = [...observations].sort((a, b) => (a.mjd_obs || 0) - (b.mjd_obs || 0));
  const currentIndex = sortedObs.findIndex((o) => o.observation_id === activeObservationId);
  const safeIndex = currentIndex >= 0 ? currentIndex : 0;
  const activeObs = sortedObs[safeIndex];

  // Playback timer stepping strictly through distinct available epochs
  useEffect(() => {
    if (isPlaying && sortedObs.length > 1) {
      timerRef.current = setInterval(() => {
        const nextIdx = (safeIndex + 1) % sortedObs.length;
        onSelectObservation(sortedObs[nextIdx].observation_id);
      }, speed * 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, safeIndex, sortedObs, speed, onSelectObservation]);

  // If active observation is removed or single epoch, stop playback
  useEffect(() => {
    if (sortedObs.length <= 1 && isPlaying) {
      setIsPlaying(false);
    }
  }, [sortedObs.length, isPlaying]);

  if (!isVisible || sortedObs.length === 0 || !activeObs) return null;

  const isSingleEpoch = sortedObs.length === 1;

  const handlePrev = () => {
    if (isSingleEpoch) return;
    const prevIdx = (safeIndex - 1 + sortedObs.length) % sortedObs.length;
    onSelectObservation(sortedObs[prevIdx].observation_id);
  };

  const handleNext = () => {
    if (isSingleEpoch) return;
    const nextIdx = (safeIndex + 1) % sortedObs.length;
    onSelectObservation(sortedObs[nextIdx].observation_id);
  };

  // Calculate irregular time delta from previous epoch
  let timeGapText = "Reference Epoch (t₀)";
  if (safeIndex > 0) {
    const prevMjd = sortedObs[safeIndex - 1].mjd_obs;
    const currMjd = activeObs.mjd_obs;
    if (prevMjd != null && currMjd != null) {
      const dtDays = currMjd - prevMjd;
      if (Math.abs(dtDays) >= 1.0) {
        timeGapText = `Δt: ${dtDays >= 0 ? "+" : ""}${dtDays.toFixed(1)} days`;
      } else {
        const dtHours = dtDays * 24.0;
        timeGapText = `Δt: ${dtHours >= 0 ? "+" : ""}${dtHours.toFixed(1)} hours`;
      }
    }
  }

  // Determine provenance badge
  const isArchive = activeObs.data_provenance?.source?.includes("IRSA") || activeObs.observation_id.startsWith("irsa_");
  const isSynthetic = Boolean(activeObs.is_synthetic_demo);

  return (
    <div className="absolute bottom-3 right-3 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark rounded-2xl p-3 shadow-2xl border border-white/10 text-xs text-slate-300 w-72 space-y-2">
        {/* Main Header / Timestamp & Epoch Counter */}
        <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
          <div className="flex items-center space-x-1.5 text-white font-bold">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[11px] truncate max-w-[150px]">
              {activeObs.date_obs ? activeObs.date_obs.slice(0, 10) : "Undated"}
            </span>
          </div>

          <div className="flex items-center space-x-1.5">
            {/* Provenance Badge */}
            {isSynthetic ? (
              <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-amber-950/80 text-amber-300 border border-amber-800/80">
                DEMO
              </span>
            ) : isArchive ? (
              <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 flex items-center space-x-0.5">
                <Database className="w-2.5 h-2.5" />
                <span>IRSA</span>
              </span>
            ) : (
              <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-slate-800/80 text-slate-300 border border-slate-700/80">
                FITS
              </span>
            )}

            {/* Epoch indicator */}
            <span className="text-[10px] text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60 font-bold">
              Epoch {safeIndex + 1} / {sortedObs.length}
            </span>
          </div>
        </div>

        {/* Detailed UTC, MJD, and Irregular Time Gap */}
        <div className="text-[10px] text-slate-400 flex items-center justify-between font-mono">
          <div>
            UTC: <span className="text-slate-200">{activeObs.date_obs ? activeObs.date_obs.slice(11, 19) : "00:00:00"}</span>
          </div>
          <div>
            MJD: <span className="text-slate-200">{activeObs.mjd_obs ? activeObs.mjd_obs.toFixed(2) : "N/A"}</span>
          </div>
        </div>

        <div className="text-[10px] text-cyan-300/90 font-mono bg-black/30 px-2 py-0.5 rounded flex items-center justify-between">
          <span className="text-slate-500 font-sans text-[9px] uppercase tracking-wider">Interval Gap:</span>
          <span>{timeGapText}</span>
        </div>

        {/* Transport Controls */}
        <div className="flex items-center justify-between pt-1 border-t border-white/10">
          <button
            onClick={handlePrev}
            disabled={isSingleEpoch}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Previous Epoch (Step back)"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsPlaying((p) => !p)}
            disabled={isSingleEpoch}
            className={`p-2 rounded-full transition-all ${
              isSingleEpoch
                ? "bg-white/5 text-slate-600 border border-white/5 cursor-not-allowed"
                : isPlaying
                ? "bg-amber-500/20 text-amber-300 border border-amber-400/50 shadow-amber-glow"
                : "bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-400/50 shadow-cyan-glow"
            }`}
            title={isSingleEpoch ? "Temporal progression disabled (Single Epoch)" : isPlaying ? "Pause Sequence" : "Play Sequence"}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>

          <button
            onClick={handleNext}
            disabled={isSingleEpoch}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Next Epoch (Step forward)"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>

          {/* Speed Selector (Delay between frames) */}
          <div className="flex items-center space-x-1 pl-2 text-[10px]">
            <span className="text-[9px] text-slate-500 mr-0.5 font-sans">Speed:</span>
            {[0.5, 1.0, 2.0].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(1.0 / s)}
                disabled={isSingleEpoch}
                className={`px-1.5 py-0.5 rounded transition-colors ${
                  Math.abs(speed - 1.0 / s) < 0.05
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/60 font-bold"
                    : "text-slate-400 hover:text-white"
                } ${isSingleEpoch ? "opacity-30 cursor-not-allowed" : ""}`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Explanatory banner if only 1 epoch is loaded */}
        {isSingleEpoch ? (
          <div className="pt-1 text-[9px] text-slate-400 text-center font-sans bg-black/20 p-1.5 rounded border border-white/5">
            Single epoch observation loaded. Load additional observation dates via the IRSA Archive or DEMO to navigate time.
          </div>
        ) : (
          /* Interactive Discrete Epoch Scrubber */
          <div className="pt-1">
            <input
              type="range"
              min="0"
              max={sortedObs.length - 1}
              step="1"
              value={safeIndex}
              onChange={(e) => {
                const idx = parseInt(e.target.value, 10);
                if (sortedObs[idx]) {
                  onSelectObservation(sortedObs[idx].observation_id);
                }
              }}
              className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
            />
            <div className="flex justify-between text-[8px] text-slate-500 px-0.5 mt-0.5 font-mono">
              <span>Epoch 1 ({sortedObs[0].date_obs ? sortedObs[0].date_obs.slice(0, 10) : "t₀"})</span>
              <span>Epoch {sortedObs.length} ({sortedObs[sortedObs.length - 1].date_obs ? sortedObs[sortedObs.length - 1].date_obs.slice(0, 10) : "tₑ"})</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
