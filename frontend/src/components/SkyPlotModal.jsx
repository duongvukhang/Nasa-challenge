import React, { useState, useMemo } from "react";
import {
  X,
  Compass,
  Maximize2,
  Calendar,
  Layers,
  ArrowRight,
  Sparkles,
  Info
} from "lucide-react";
import { getStableTrackColor } from "../utils/colors";

export const SkyPlotModal = ({
  isOpen,
  onClose,
  track,
  onSelectObservation
}) => {
  const [viewMode, setViewMode] = useState("relative"); // "relative" (arcsec from ref) | "absolute" (deg)
  const [hoveredPoint, setHoveredPoint] = useState(null);

  if (!isOpen || !track) return null;

  const trackColor = track.color || getStableTrackColor(track.track_id);
  const timeline = track.timeline || [];
  const measuredPoints = timeline.filter((ep) => ep.is_measured && ep.ra_deg != null && ep.dec_deg != null);

  // Compute reference coordinates
  const refRa = track.reference_ra_deg;
  const refDec = track.reference_dec_deg;

  // Transform coordinates for plotting
  // If "relative": dx = -(ra - refRa)*cos(refDec)*3600 (arcsec, East is positive/left), dy = (dec - refDec)*3600
  // If "absolute": x = ra (deg), y = dec (deg)
  const plotData = useMemo(() => {
    if (measuredPoints.length === 0) return [];

    const cosDec = Math.cos((refDec * Math.PI) / 180.0) || 1.0;

    return measuredPoints.map((ep, idx) => {
      const isRef = ep.observation_id === track.reference_observation_id;
      const sigmaArcsec = ep.position_uncertainty_arcsec || 0.5;

      let x, y, xErr, yErr;
      if (viewMode === "relative") {
        // Astronomical convention: East is left, so +X is East (-dRA)
        x = -(ep.ra_deg - refRa) * cosDec * 3600.0;
        y = (ep.dec_deg - refDec) * 3600.0;
        xErr = sigmaArcsec;
        yErr = sigmaArcsec;
      } else {
        x = ep.ra_deg;
        y = ep.dec_deg;
        xErr = sigmaArcsec / (3600.0 * cosDec);
        yErr = sigmaArcsec / 3600.0;
      }

      return {
        epochIdx: idx + 1,
        obsId: ep.observation_id,
        dateObs: ep.date_obs,
        mjdObs: ep.mjd_obs,
        ra: ep.ra_deg,
        dec: ep.dec_deg,
        band: ep.band || "LVF",
        isRef,
        status: ep.status,
        x,
        y,
        xErr,
        yErr,
        sigmaArcsec
      };
    });
  }, [measuredPoints, refRa, refDec, viewMode, track.reference_observation_id]);

  // Compute bounding box for SVG canvas (with comfortable padding)
  const bounds = useMemo(() => {
    if (plotData.length === 0) {
      return { minX: -5, maxX: 5, minY: -5, maxY: 5 };
    }
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    plotData.forEach((p) => {
      minX = Math.min(minX, p.x - p.xErr);
      maxX = Math.max(maxX, p.x + p.xErr);
      minY = Math.min(minY, p.y - p.yErr);
      maxY = Math.max(maxY, p.y + p.yErr);
    });

    // Ensure non-zero range
    if (maxX - minX < 1e-4) {
      const pad = viewMode === "relative" ? 3 : 0.001;
      minX -= pad;
      maxX += pad;
    }
    if (maxY - minY < 1e-4) {
      const pad = viewMode === "relative" ? 3 : 0.001;
      minY -= pad;
      maxY += pad;
    }

    const padX = (maxX - minX) * 0.2;
    const padY = (maxY - minY) * 0.2;
    return {
      minX: minX - padX,
      maxX: maxX + padX,
      minY: minY - padY,
      maxY: maxY + padY
    };
  }, [plotData, viewMode]);

  // SVG dimensions
  const svgWidth = 600;
  const svgHeight = 440;
  const margin = { top: 30, right: 30, bottom: 50, left: 60 };
  const innerW = svgWidth - margin.left - margin.right;
  const innerH = svgHeight - margin.top - margin.bottom;

  // Scale map functions
  const scaleX = (val) => {
    // In relative mode, higher x is East (left) or conventional plot
    const range = bounds.maxX - bounds.minX;
    return margin.left + ((val - bounds.minX) / range) * innerW;
  };

  const scaleY = (val) => {
    // Canvas y is 0 at top, so flip y
    const range = bounds.maxY - bounds.minY;
    return margin.top + innerH - ((val - bounds.minY) / range) * innerH;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/75 backdrop-blur-sm pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark border border-white/15 rounded-2xl w-full max-w-3xl flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        
        {/* Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between bg-black/40">
          <div className="flex items-center space-x-3">
            <div
              className="w-4 h-4 rounded-full shadow-lg"
              style={{ backgroundColor: trackColor, boxShadow: `0 0 10px ${trackColor}` }}
            />
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-white font-bold text-sm">Historical Sky-Coordinate Plot</span>
                <span className="text-xs text-cyan-300 font-sans">{track.track_id}</span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans">
                Measured positions across {measuredPoints.length} confirmed epochs with 1σ error bars
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* View Mode Toggle */}
            <div className="flex rounded-lg bg-black/40 p-0.5 border border-white/10 text-xs font-sans">
              <button
                onClick={() => setViewMode("relative")}
                className={`px-2 py-1 rounded-md transition-colors ${
                  viewMode === "relative"
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/50"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Δ Arcsec (Relative)
              </button>
              <button
                onClick={() => setViewMode("absolute")}
                className={`px-2 py-1 rounded-md transition-colors ${
                  viewMode === "absolute"
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/50"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                J2000 Degrees
              </button>
            </div>

            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Plot Area */}
        <div className="relative p-4 flex flex-col items-center justify-center bg-black/30">
          {plotData.length === 0 ? (
            <div className="py-20 text-center text-slate-400 text-xs font-sans">
              No measured detections available to plot for this track.
            </div>
          ) : (
            <svg
              width={svgWidth}
              height={svgHeight}
              className="overflow-visible select-none"
            >
              <defs>
                <marker
                  id="plotArrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="4"
                  markerHeight="4"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={trackColor} />
                </marker>
              </defs>

              {/* Grid background */}
              <rect
                x={margin.left}
                y={margin.top}
                width={innerW}
                height={innerH}
                fill="rgba(0, 0, 0, 0.4)"
                stroke="rgba(255, 255, 255, 0.1)"
                strokeWidth={1}
              />

              {/* Grid Lines */}
              {[0.25, 0.5, 0.75].map((frac, i) => (
                <React.Fragment key={i}>
                  <line
                    x1={margin.left + innerW * frac}
                    y1={margin.top}
                    x2={margin.left + innerW * frac}
                    y2={margin.top + innerH}
                    stroke="rgba(255, 255, 255, 0.05)"
                    strokeDasharray="3,3"
                  />
                  <line
                    x1={margin.left}
                    y1={margin.top + innerH * frac}
                    x2={margin.left + innerW}
                    y2={margin.top + innerH * frac}
                    stroke="rgba(255, 255, 255, 0.05)"
                    strokeDasharray="3,3"
                  />
                </React.Fragment>
              ))}

              {/* Reference Crosshair at (0, 0) if in relative mode */}
              {viewMode === "relative" && bounds.minX <= 0 && bounds.maxX >= 0 && bounds.minY <= 0 && bounds.maxY >= 0 && (
                <g opacity={0.3}>
                  <line
                    x1={scaleX(0)}
                    y1={margin.top}
                    x2={scaleX(0)}
                    y2={margin.top + innerH}
                    stroke="#22d3ee"
                    strokeWidth={1}
                  />
                  <line
                    x1={margin.left}
                    y1={scaleY(0)}
                    x2={margin.left + innerW}
                    y2={scaleY(0)}
                    stroke="#22d3ee"
                    strokeWidth={1}
                  />
                </g>
              )}

              {/* Trajectory connection lines between chronological detections */}
              {plotData.map((pt, idx) => {
                if (idx === 0) return null;
                const prev = plotData[idx - 1];
                const x1 = scaleX(prev.x);
                const y1 = scaleY(prev.y);
                const x2 = scaleX(pt.x);
                const y2 = scaleY(pt.y);
                const isLast = idx === plotData.length - 1;

                return (
                  <line
                    key={`line_${idx}`}
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={trackColor}
                    strokeWidth={1.5}
                    strokeDasharray="4,3"
                    opacity={0.8}
                    markerEnd={isLast ? "url(#plotArrow)" : undefined}
                  />
                );
              })}

              {/* Detections with 1-sigma error bars */}
              {plotData.map((pt) => {
                const cx = scaleX(pt.x);
                const cy = scaleY(pt.y);
                const errPxX = Math.abs(scaleX(pt.x + pt.xErr) - cx);
                const errPxY = Math.abs(scaleY(pt.y + pt.yErr) - cy);

                return (
                  <g
                    key={pt.obsId}
                    onMouseEnter={() => setHoveredPoint(pt)}
                    onMouseLeave={() => setHoveredPoint(null)}
                    onClick={() => onSelectObservation?.(pt.obsId)}
                    className="cursor-pointer"
                  >
                    {/* Error bars along X and Y */}
                    <line
                      x1={cx - errPxX}
                      y1={cy}
                      x2={cx + errPxX}
                      y2={cy}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />
                    <line
                      x1={cx}
                      y1={cy - errPxY}
                      x2={cx}
                      y2={cy + errPxY}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />

                    {/* Cap lines for error bars */}
                    <line
                      x1={cx - errPxX}
                      y1={cy - 3}
                      x2={cx - errPxX}
                      y2={cy + 3}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />
                    <line
                      x1={cx + errPxX}
                      y1={cy - 3}
                      x2={cx + errPxX}
                      y2={cy + 3}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />
                    <line
                      x1={cx - 3}
                      y1={cy - errPxY}
                      x2={cx + 3}
                      y2={cy - errPxY}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />
                    <line
                      x1={cx - 3}
                      y1={cy + errPxY}
                      x2={cx + 3}
                      y2={cy + errPxY}
                      stroke={trackColor}
                      strokeWidth={1}
                      opacity={0.6}
                    />

                    {/* Point Marker */}
                    {pt.isRef ? (
                      // Diamond for reference epoch
                      <polygon
                        points={`${cx},${cy - 5} ${cx + 5},${cy} ${cx},${cy + 5} ${cx - 5},${cy}`}
                        fill="#ffffff"
                        stroke={trackColor}
                        strokeWidth={1.5}
                      />
                    ) : (
                      // Circle for matched epochs
                      <circle
                        cx={cx}
                        cy={cy}
                        r={4}
                        fill={trackColor}
                        stroke="#ffffff"
                        strokeWidth={1}
                      />
                    )}

                    {/* Epoch label */}
                    <text
                      x={cx + 6}
                      y={cy - 5}
                      fill={pt.isRef ? "#ffffff" : "#94a3b8"}
                      fontSize={10}
                      fontFamily="monospace"
                      fontWeight={pt.isRef ? "bold" : "normal"}
                    >
                      E{pt.epochIdx}
                    </text>
                  </g>
                );
              })}

              {/* Axis Labels */}
              <text
                x={margin.left + innerW / 2}
                y={svgHeight - 12}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={11}
                fontFamily="sans-serif"
              >
                {viewMode === "relative" ? "ΔRA cos(Dec) [arcsec] (East ← / West →)" : "Right Ascension J2000 [deg]"}
              </text>

              <text
                transform={`rotate(-90)`}
                x={-(margin.top + innerH / 2)}
                y={18}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={11}
                fontFamily="sans-serif"
              >
                {viewMode === "relative" ? "ΔDec [arcsec] (North ↑ / South ↓)" : "Declination J2000 [deg]"}
              </text>

              {/* Axis Tick Values */}
              <text x={margin.left} y={margin.top + innerH + 16} fill="#64748b" fontSize={9}>
                {bounds.minX.toFixed(viewMode === "relative" ? 1 : 4)}
              </text>
              <text x={margin.left + innerW} y={margin.top + innerH + 16} textAnchor="end" fill="#64748b" fontSize={9}>
                {bounds.maxX.toFixed(viewMode === "relative" ? 1 : 4)}
              </text>
              <text x={margin.left - 6} y={margin.top + innerH} textAnchor="end" fill="#64748b" fontSize={9}>
                {bounds.minY.toFixed(viewMode === "relative" ? 1 : 4)}
              </text>
              <text x={margin.left - 6} y={margin.top + 8} textAnchor="end" fill="#64748b" fontSize={9}>
                {bounds.maxY.toFixed(viewMode === "relative" ? 1 : 4)}
              </text>
            </svg>
          )}

          {/* Hover Tooltip */}
          {hoveredPoint && (
            <div className="absolute top-6 right-6 bg-black/90 border border-white/20 rounded-xl p-3 shadow-2xl text-xs space-y-1 z-10 pointer-events-none">
              <div className="flex items-center space-x-2">
                <span className="font-bold text-white">Epoch {hoveredPoint.epochIdx}</span>
                {hoveredPoint.isRef && (
                  <span className="px-1 rounded bg-cyan-500/20 text-cyan-300 text-[10px]">
                    REFERENCE E0
                  </span>
                )}
                <span className="text-slate-400 font-sans">{hoveredPoint.band}</span>
              </div>
              <div className="text-slate-300">
                RA: <span className="text-white font-mono">{hoveredPoint.ra.toFixed(5)}°</span>
              </div>
              <div className="text-slate-300">
                Dec: <span className="text-white font-mono">{hoveredPoint.dec.toFixed(5)}°</span>
              </div>
              <div className="text-cyan-400">
                1σ Pos Error: ±{hoveredPoint.sigmaArcsec.toFixed(3)}″
              </div>
              <div className="text-slate-400 text-[10px]">
                Date: {hoveredPoint.dateObs ? hoveredPoint.dateObs.slice(0, 19) : "N/A"}
              </div>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-white/10 bg-black/50 flex items-center justify-between text-xs font-sans text-slate-400">
          <div className="flex items-center space-x-3">
            <span className="flex items-center space-x-1">
              <span className="inline-block w-2.5 h-2.5 bg-white transform rotate-45 mr-1" />
              <span>Reference Epoch (E0)</span>
            </span>
            <span className="flex items-center space-x-1">
              <span
                className="inline-block w-2.5 h-2.5 rounded-full mr-1"
                style={{ backgroundColor: trackColor }}
              />
              <span>Confirmed Detections</span>
            </span>
          </div>
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
