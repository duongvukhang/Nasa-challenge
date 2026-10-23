import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Calendar,
  Clock,
  ChevronDown,
  ChevronUp
} from "lucide-react";

export const TimeController = ({
  observations = [],
  activeObservationId,
  onSelectObservation,
  isVisible = true
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1.0); // seconds per epoch
  const [isExpanded, setIsExpanded] = useState(false);
  const timerRef = useRef(null);

  // Chronologically sorted observations
  const sortedObs = [...observations].sort((a, b) => (a.mjd_obs || 0) - (b.mjd_obs || 0));
  const currentIndex = sortedObs.findIndex((o) => o.observation_id === activeObservationId);

  // Playback timer
  useEffect(() => {
    if (isPlaying && sortedObs.length > 1) {
      timerRef.current = setInterval(() => {
        const nextIdx = (currentIndex + 1) % sortedObs.length;
        onSelectObservation(sortedObs[nextIdx].observation_id);
      }, speed * 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, currentIndex, sortedObs, speed, onSelectObservation]);

  if (!isVisible || sortedObs.length === 0) return null;

  const activeObs = sortedObs[currentIndex] || sortedObs[0];

  const handlePrev = () => {
    const prevIdx = (currentIndex - 1 + sortedObs.length) % sortedObs.length;
    onSelectObservation(sortedObs[prevIdx].observation_id);
  };

  const handleNext = () => {
    const nextIdx = (currentIndex + 1) % sortedObs.length;
    onSelectObservation(sortedObs[nextIdx].observation_id);
  };

  return (
    <div className="absolute bottom-3 right-3 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass rounded-2xl p-2.5 shadow-2xl border border-white/10 text-xs text-slate-300 w-64 space-y-2">
        {/* Main Header / Timestamp */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 text-white font-bold">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[11px] truncate max-w-[140px]">
              {activeObs.date_obs ? activeObs.date_obs.slice(0, 10) : "Undated"}
            </span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
              activeObs.is_synthetic_demo
                ? "bg-amber-950/80 text-amber-300 border border-amber-800/80"
                : "bg-cyan-950/80 text-cyan-300 border border-cyan-800/80"
            }`}>
              {activeObs.is_synthetic_demo ? "DEMO" : "REAL"}
            </span>
            <span className="text-[10px] text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60">
              {currentIndex + 1} / {sortedObs.length}
            </span>
          </div>
        </div>

        {/* Detailed UTC & MJD */}
        <div className="text-[10px] text-slate-400 flex justify-between">
          <span>UTC: {activeObs.date_obs ? activeObs.date_obs.slice(11, 19) : "00:00:00"}</span>
          <span>MJD: {activeObs.mjd_obs ? activeObs.mjd_obs.toFixed(2) : "N/A"}</span>
        </div>

        {/* Transport Controls */}
        <div className="flex items-center justify-between pt-1 border-t border-white/10">
          <button
            onClick={handlePrev}
            className="p-1 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
            title="Previous Epoch"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsPlaying((p) => !p)}
            className="p-1.5 rounded-full bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-400/50 shadow-cyan-glow transition-all"
            title={isPlaying ? "Pause" : "Play Sequence"}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>

          <button
            onClick={handleNext}
            className="p-1 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
            title="Next Epoch"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>

          {/* Speed Selector */}
          <div className="flex items-center space-x-1 pl-2 text-[10px]">
            {[0.5, 1.0, 2.0].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(1.0 / s)}
                className={`px-1 py-0.5 rounded transition-colors ${
                  Math.abs(speed - 1.0 / s) < 0.05
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/60 font-bold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Interactive scrubber */}
        {sortedObs.length > 1 && (
          <div className="pt-1">
            <input
              type="range"
              min="0"
              max={sortedObs.length - 1}
              step="1"
              value={currentIndex >= 0 ? currentIndex : 0}
              onChange={(e) => onSelectObservation(sortedObs[parseInt(e.target.value)].observation_id)}
              className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
            />
          </div>
        )}
      </div>
    </div>
  );
};
