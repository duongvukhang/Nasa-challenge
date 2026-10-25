import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Play,
  Pause,
  SkipForward,
  AlertTriangle,
  RotateCw,
  GitCompare,
  Columns2,
  Eye,
  Layers,
  Compass,
  CheckCircle2,
  XCircle,
  Sliders
} from "lucide-react";
import { api } from "../services/api";
import { getStableTrackColor } from "../utils/colors";

export const ComparisonViewer = ({
  viewMode = "split", // "split" | "blink" | "difference"
  targetObservation,
  referenceObservation,
  sources = [],
  selectedSource,
  onSelectSource,
  tracks = {},
  activeTrackId,
  onSelectTrack,
  hiddenTrackIds = new Set(),
  overlaySettings = {},
  displaySettings = {},
  onChangeViewMode
}) => {
  // Shared Zoom & Pan for synchronized exploration
  const [scale, setScale] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);

  // Blink mode state
  const [blinkActiveIndex, setBlinkActiveIndex] = useState(0); // 0 = target, 1 = reference
  const [isBlinkPlaying, setIsBlinkPlaying] = useState(true);
  const [blinkSpeedMs, setBlinkSpeedMs] = useState(500);

  // Difference imaging state
  const [diffMeta, setDiffMeta] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState(null);
  const [diffColormap, setDiffColormap] = useState("coolwarm");

  // Reset zoom & pan
  const handleResetView = useCallback(() => {
    setScale(1.0);
    setPan({ x: 0, y: 0 });
  }, []);

  // Zoom with scroll wheel
  const handleWheel = (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    setScale((prev) => Math.min(12.0, Math.max(0.3, prev * factor)));
  };

  // Drag start
  const handleMouseDown = (e) => {
    if (e.button === 0) {
      setIsDragging(true);
      dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Blink interval timer
  useEffect(() => {
    if (viewMode !== "blink" || !isBlinkPlaying) return;

    const timer = setInterval(() => {
      setBlinkActiveIndex((prev) => (prev === 0 ? 1 : 0));
    }, blinkSpeedMs);

    return () => clearInterval(timer);
  }, [viewMode, isBlinkPlaying, blinkSpeedMs]);

  // Load difference imaging compatibility when difference mode is active
  useEffect(() => {
    if (viewMode !== "difference" || !targetObservation?.observation_id || !referenceObservation?.observation_id) {
      return;
    }

    let isSubscribed = true;
    setDiffLoading(true);
    setDiffError(null);

    api
      .getDifference(targetObservation.observation_id, referenceObservation.observation_id)
      .then((res) => {
        if (!isSubscribed) return;
        setDiffMeta(res);
        setDiffLoading(false);
      })
      .catch((err) => {
        if (!isSubscribed) return;
        setDiffError(err.message || "Failed to evaluate difference imaging");
        setDiffLoading(false);
      });

    return () => {
      isSubscribed = false;
    };
  }, [viewMode, targetObservation?.observation_id, referenceObservation?.observation_id]);

  if (!targetObservation || !referenceObservation) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-space-950 text-slate-400 p-6 select-none">
        <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-1">
          Comparison Requires Two Observations
        </h3>
        <p className="text-xs max-w-sm text-center text-slate-400">
          Load at least two distinct epochs from the IRSA archive or sample dataset to compare observations across time.
        </p>
      </div>
    );
  }

  const targetImageUrl = api.getImageUrl(targetObservation.observation_id, {
    stretch: displaySettings.stretch || "asinh",
    colormap: displaySettings.colormap || "inferno",
    brightness: displaySettings.brightness ?? 1.0,
    contrast: displaySettings.contrast ?? 1.0,
    p_min: displaySettings.p_min ?? 0.5,
    p_max: displaySettings.p_max ?? 99.5,
    max_dim: 1200
  });

  const refImageUrl = api.getImageUrl(referenceObservation.observation_id, {
    stretch: displaySettings.stretch || "asinh",
    colormap: displaySettings.colormap || "inferno",
    brightness: displaySettings.brightness ?? 1.0,
    contrast: displaySettings.contrast ?? 1.0,
    p_min: displaySettings.p_min ?? 0.5,
    p_max: displaySettings.p_max ?? 99.5,
    max_dim: 1200
  });

  const diffImageUrl = api.getDifferenceImageUrl(
    targetObservation.observation_id,
    referenceObservation.observation_id,
    { colormap: diffColormap, max_dim: 1200 }
  );

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className={`w-full h-full relative overflow-hidden bg-space-950 select-none ${
        isDragging ? "cursor-grabbing-sky" : "cursor-crosshair-sky"
      }`}
    >
      {/* ========================================================
          1. SPLIT VIEW: Synchronized Side-by-Side Dual Viewports
         ======================================================== */}
      {viewMode === "split" && (
        <div className="grid grid-cols-2 w-full h-full divide-x divide-white/10">
          {/* Left Pane: Target Observation */}
          <div className="relative w-full h-full overflow-hidden flex items-center justify-center bg-space-950">
            {/* Header Badge */}
            <div className="absolute top-14 left-4 z-20 stellarium-glass rounded-full px-3 py-1 flex items-center space-x-2 text-[11px] font-mono shadow-xl border border-cyan-500/30">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="font-bold text-cyan-300">TARGET (T0):</span>
              <span className="text-white font-bold">{targetObservation.observation_id}</span>
              <span className="text-slate-400">|</span>
              <span className="text-cyan-200">{targetObservation.band || "LVF"}</span>
              {targetObservation.date_obs && (
                <>
                  <span className="text-slate-400">|</span>
                  <span className="text-slate-300">{targetObservation.date_obs.slice(0, 10)}</span>
                </>
              )}
              <span className="text-[9px] text-slate-400 bg-white/5 px-1.5 py-0.5 rounded hidden xl:inline">Pixel-Synchronized</span>
            </div>

            {/* Canvas Image */}
            <div
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
                transformOrigin: "center center",
                transition: isDragging ? "none" : "transform 0.05s ease-out"
              }}
              className="relative"
            >
              <img
                src={targetImageUrl}
                alt={`Target ${targetObservation.observation_id}`}
                draggable={false}
                className="block max-w-[85vw] max-h-[85vh] object-contain shadow-2xl select-none pointer-events-none"
              />
            </div>
          </div>

          {/* Right Pane: Reference Observation */}
          <div className="relative w-full h-full overflow-hidden flex items-center justify-center bg-space-950">
            {/* Header Badge */}
            <div className="absolute top-14 left-4 z-20 stellarium-glass rounded-full px-3 py-1 flex items-center space-x-2 text-[11px] font-mono shadow-xl border border-amber-500/30">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span className="font-bold text-amber-300">REFERENCE (T1):</span>
              <span className="text-white font-bold">{referenceObservation.observation_id}</span>
              <span className="text-slate-400">|</span>
              <span className="text-amber-200">{referenceObservation.band || "LVF"}</span>
              {referenceObservation.date_obs && (
                <>
                  <span className="text-slate-400">|</span>
                  <span className="text-slate-300">{referenceObservation.date_obs.slice(0, 10)}</span>
                </>
              )}
              <span className="text-[9px] text-slate-400 bg-white/5 px-1.5 py-0.5 rounded hidden xl:inline">Pixel-Synchronized</span>
            </div>

            {/* Canvas Image (Synchronously Panned & Zoomed) */}
            <div
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
                transformOrigin: "center center",
                transition: isDragging ? "none" : "transform 0.05s ease-out"
              }}
              className="relative"
            >
              <img
                src={refImageUrl}
                alt={`Reference ${referenceObservation.observation_id}`}
                draggable={false}
                className="block max-w-[85vw] max-h-[85vh] object-contain shadow-2xl select-none pointer-events-none"
              />
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          2. BLINK VIEW: Single Viewport Alternating Rapidly
         ======================================================== */}
      {viewMode === "blink" && (
        <div className="relative w-full h-full flex items-center justify-center bg-space-950">
          {/* Active Epoch Floating Header Indicator */}
          <div className="absolute top-14 left-1/2 -translate-x-1/2 z-20 stellarium-glass rounded-full px-4 py-1.5 flex items-center space-x-3 text-xs font-mono shadow-2xl border border-white/10">
            <div className="flex items-center space-x-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  blinkActiveIndex === 0
                    ? "bg-cyan-400 shadow-cyan-glow animate-pulse"
                    : "bg-amber-400 shadow-amber-glow"
                }`}
              />
              <span className="font-bold uppercase tracking-wider text-white">
                {blinkActiveIndex === 0 ? "Target Epoch" : "Reference Epoch"}
              </span>
            </div>
            <span className="text-slate-500">|</span>
            <span className={blinkActiveIndex === 0 ? "text-cyan-300 font-bold" : "text-amber-300 font-bold"}>
              {blinkActiveIndex === 0
                ? `${targetObservation.observation_id} (${targetObservation.date_obs?.slice(0, 10)})`
                : `${referenceObservation.observation_id} (${referenceObservation.date_obs?.slice(0, 10)})`}
            </span>
          </div>

          {/* Canvas Image Alternating */}
          <div
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
              transformOrigin: "center center",
              transition: isDragging ? "none" : "transform 0.05s ease-out"
            }}
            className="relative"
          >
            <img
              src={blinkActiveIndex === 0 ? targetImageUrl : refImageUrl}
              alt="Blink Observation"
              draggable={false}
              className="block max-w-[85vw] max-h-[85vh] object-contain shadow-2xl select-none pointer-events-none"
            />
          </div>

          {/* Floating Blink Control Bar */}
          <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-30 stellarium-glass rounded-full px-3 py-1.5 flex items-center space-x-2 shadow-2xl font-mono text-xs">
            <button
              onClick={() => setIsBlinkPlaying(!isBlinkPlaying)}
              className="p-1 rounded-full bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 transition-colors"
              title={isBlinkPlaying ? "Pause Blink" : "Play Blink"}
            >
              {isBlinkPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => {
                setIsBlinkPlaying(false);
                setBlinkActiveIndex((prev) => (prev === 0 ? 1 : 0));
              }}
              className="p-1 rounded-full hover:bg-white/10 text-slate-300 transition-colors"
              title="Step Single Epoch"
            >
              <SkipForward className="w-3.5 h-3.5" />
            </button>
            <div className="border-l border-white/10 pl-2 flex items-center space-x-1 text-[11px]">
              <span className="text-slate-400 mr-1">Rate:</span>
              {[200, 500, 1000].map((ms) => (
                <button
                  key={ms}
                  onClick={() => setBlinkSpeedMs(ms)}
                  className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                    blinkSpeedMs === ms
                      ? "bg-cyan-500/30 text-cyan-300 border border-cyan-500/50"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {ms}ms
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          3. DIFFERENCE VIEW: Gated Scientific Difference Imaging
         ======================================================== */}
      {viewMode === "difference" && (
        <div className="relative w-full h-full flex items-center justify-center bg-space-950">
          {diffLoading && (
            <div className="text-center text-slate-400 font-mono text-xs space-y-2">
              <RotateCw className="w-6 h-6 animate-spin mx-auto text-cyan-400" />
              <p>Evaluating WCS alignment & computing scientific difference...</p>
            </div>
          )}

          {!diffLoading && diffMeta?.compatible === false && (
            <div className="max-w-md stellarium-glass-dark rounded-2xl p-6 border border-amber-500/40 shadow-2xl text-center space-y-4 font-mono">
              <div className="w-12 h-12 rounded-full bg-amber-950/60 border border-amber-500/40 flex items-center justify-center text-amber-400 mx-auto">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Difference Imaging Refused on Scientific Grounds
              </h3>
              <p className="text-xs text-amber-200/90 leading-relaxed bg-amber-950/40 p-3 rounded-lg border border-amber-900/50">
                {diffMeta.reason || "Observations are scientifically incompatible for image subtraction."}
              </p>
              <div className="text-[11px] text-slate-400 text-left space-y-1 bg-space-900/60 p-3 rounded border border-white/5">
                <div>• Target: <span className="text-cyan-300">{targetObservation.observation_id}</span> ({targetObservation.band})</div>
                <div>• Reference: <span className="text-amber-300">{referenceObservation.observation_id}</span> ({referenceObservation.band})</div>
                <div>• Principle: <span className="text-slate-300">SkyTrace prohibits subtracting incompatible spectral channels to prevent false artifact interpretation.</span></div>
              </div>
              <div className="pt-2 flex items-center justify-center space-x-2">
                <button
                  onClick={() => onChangeViewMode("split")}
                  className="px-3 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 text-xs flex items-center space-x-1.5"
                >
                  <Columns2 className="w-3.5 h-3.5" />
                  <span>Use Split Mode</span>
                </button>
                <button
                  onClick={() => onChangeViewMode("blink")}
                  className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-200 text-xs flex items-center space-x-1.5"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  <span>Use Blink Mode</span>
                </button>
              </div>
            </div>
          )}

          {!diffLoading && diffMeta?.compatible === true && (
            <>
              {/* Header Info */}
              <div className="absolute top-14 left-1/2 -translate-x-1/2 z-20 stellarium-glass rounded-full px-4 py-1.5 flex items-center space-x-3 text-xs font-mono shadow-2xl border border-cyan-500/30">
                <div className="flex items-center space-x-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-cyan-glow" />
                  <span className="font-bold text-white uppercase">Difference Image:</span>
                  <span className="text-cyan-300">{targetObservation.observation_id}</span>
                  <span className="text-slate-400">−</span>
                  <span className="text-amber-300">{referenceObservation.observation_id}</span>
                </div>
                <span className="text-slate-500">|</span>
                <span className="text-slate-300">Band: {targetObservation.band}</span>
              </div>

              {/* Difference Canvas */}
              <div
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
                  transformOrigin: "center center",
                  transition: isDragging ? "none" : "transform 0.05s ease-out"
                }}
                className="relative"
              >
                <img
                  src={diffImageUrl}
                  alt="Difference Image"
                  draggable={false}
                  className="block max-w-[85vw] max-h-[85vh] object-contain shadow-2xl select-none pointer-events-none"
                />
              </div>

              {/* Statistics & Colormap Floating Panel */}
              <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-30 stellarium-glass rounded-full px-4 py-1.5 flex items-center space-x-4 shadow-2xl font-mono text-[11px] text-slate-300">
                <div>
                  <span className="text-slate-500">Mean: </span>
                  <span className="text-white font-bold">{diffMeta.mean_difference}</span>
                </div>
                <div>
                  <span className="text-slate-500">Median: </span>
                  <span className="text-white font-bold">{diffMeta.median_difference}</span>
                </div>
                <div>
                  <span className="text-slate-500">Noise (Std σ): </span>
                  <span className="text-cyan-300 font-bold">{diffMeta.std_difference}</span>
                </div>
                <div className="border-l border-white/10 pl-3 flex items-center space-x-1">
                  <span className="text-slate-400 mr-1">Colormap:</span>
                  {["coolwarm", "RdBu_r", "gray"].map((cm) => (
                    <button
                      key={cm}
                      onClick={() => setDiffColormap(cm)}
                      className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                        diffColormap === cm
                          ? "bg-cyan-500/30 text-cyan-300 border border-cyan-500/50"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      {cm}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Floating Zoom & Fit Controls (Right side) */}
      <div className="absolute right-3 top-16 flex flex-col space-y-1.5 pointer-events-auto select-none z-30">
        <div className="stellarium-glass rounded-xl p-1 shadow-lg flex flex-col space-y-1 text-slate-300">
          <button
            onClick={() => setScale((s) => Math.min(12.0, s * 1.25))}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setScale((s) => Math.max(0.3, s / 1.25))}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleResetView}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
