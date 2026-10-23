import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Crosshair,
  Compass,
  Sparkles,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { api } from "../services/api";

export const SkyViewer = ({
  observation,
  sources = [],
  selectedSource,
  onSelectSource,
  overlaySettings = {},
  displaySettings = {},
  trackData = null,
  predictionData = null,
  isLoading = false
}) => {
  // Zoom & Pan state
  const [scale, setScale] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  // Dynamic cursor celestial coordinate readout
  const [cursorPos, setCursorPos] = useState(null);

  // Reset view to center and fit
  const handleResetView = useCallback(() => {
    setScale(1.0);
    setPan({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    handleResetView();
  }, [observation?.observation_id, handleResetView]);

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

  // Drag move & hover coordinates calculation
  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y
      });
    }

    if (imgRef.current && observation) {
      const imgRect = imgRef.current.getBoundingClientRect();
      const [imgHeight, imgWidth] = observation.image_shape || [2048, 2048];

      if (
        e.clientX >= imgRect.left &&
        e.clientX <= imgRect.right &&
        e.clientY >= imgRect.top &&
        e.clientY <= imgRect.bottom &&
        imgRect.width > 0 &&
        imgRect.height > 0
      ) {
        const normX = (e.clientX - imgRect.left) / imgRect.width;
        const normY = (e.clientY - imgRect.top) / imgRect.height;
        const px = normX * imgWidth;
        const py = (1.0 - normY) * imgHeight; // astronomical display flips vertical axis

        let ra = null, dec = null;
        if (observation.wcs?.has_wcs && observation.wcs.crval && observation.wcs.crpix && observation.wcs.pixel_scale_arcsec) {
          const dx = px - observation.wcs.crpix[0];
          const dy = py - observation.wcs.crpix[1];
          const degPerPix = observation.wcs.pixel_scale_arcsec / 3600.0;
          const cosDec = Math.cos((observation.wcs.crval[1] * Math.PI) / 180.0) || 1.0;
          ra = (observation.wcs.crval[0] - (dx * degPerPix) / cosDec + 360) % 360;
          dec = Math.max(-90, Math.min(90, observation.wcs.crval[1] + dy * degPerPix));
        }

        setCursorPos({ px, py, ra, dec });
      } else {
        setCursorPos(null);
      }
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  if (!observation) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-space-950 text-center select-none relative p-6">
        <div className="w-16 h-16 rounded-2xl bg-cyan-950/40 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4 shadow-cyan-glow">
          <Compass className="w-8 h-8 opacity-70 animate-pulse" />
        </div>
        <h2 className="text-base font-bold text-white tracking-widest uppercase mb-1">
          SPHEREx Observatory Standby
        </h2>
        <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
          Open the left sidebar or select from the top actions to explore real infrared observations or simulated demonstrations.
        </p>
      </div>
    );
  }

  const [imgH, imgW] = observation.image_shape || [2048, 2048];
  const imageUrl = api.getImageUrl(observation.observation_id, {
    stretch: displaySettings.stretch || "asinh",
    colormap: displaySettings.colormap || "inferno",
    brightness: displaySettings.brightness ?? 1.0,
    contrast: displaySettings.contrast ?? 1.0,
    p_min: displaySettings.p_min ?? 0.5,
    p_max: displaySettings.p_max ?? 99.5,
    max_dim: 1400
  });

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className={`w-full h-full relative overflow-hidden bg-space-950 flex items-center justify-center select-none ${
        isDragging ? "cursor-grabbing-sky" : "cursor-crosshair-sky"
      }`}
    >
      {/* Transform Container */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
          transformOrigin: "center center",
          transition: isDragging ? "none" : "transform 0.05s ease-out"
        }}
        className="relative"
      >
        <img
          ref={imgRef}
          src={imageUrl}
          alt={`SPHEREx Observation ${observation.filename}`}
          draggable={false}
          className="max-w-[85vw] max-h-[85vh] object-contain shadow-2xl rounded-xs pointer-events-none border border-white/5"
        />

        {/* Scientific Overlays (SVG) */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox={`0 0 ${imgW} ${imgH}`}
          preserveAspectRatio="none"
        >
          {/* 1. Coordinate Grid Lines (When enabled) */}
          {overlaySettings.showGrid && (
            <g className="pointer-events-none opacity-40">
              {/* Grid lines along X & Y */}
              {[0.2, 0.4, 0.6, 0.8].map((frac, idx) => (
                <React.Fragment key={idx}>
                  <line
                    x1={imgW * frac}
                    y1={0}
                    x2={imgW * frac}
                    y2={imgH}
                    stroke="rgba(34, 211, 238, 0.4)"
                    strokeWidth={1}
                    strokeDasharray="4,4"
                  />
                  <line
                    x1={0}
                    y1={imgH * frac}
                    x2={imgW}
                    y2={imgH * frac}
                    stroke="rgba(34, 211, 238, 0.4)"
                    strokeWidth={1}
                    strokeDasharray="4,4"
                  />
                </React.Fragment>
              ))}
            </g>
          )}

          {/* 2. Tracking Trajectory Lines (When tracking and enabled) */}
          {overlaySettings.showTrajectories && trackData?.timeline?.length > 1 && (
            <g className="pointer-events-none">
              {/* Draw polyline connecting epoch positions */}
              {trackData.timeline.map((ep, idx) => {
                if (idx === 0) return null;
                const prev = trackData.timeline[idx - 1];
                if (prev.pixel_x == null || ep.pixel_x == null) return null;
                const sx1 = prev.pixel_x;
                const sy1 = imgH - prev.pixel_y;
                const sx2 = ep.pixel_x;
                const sy2 = imgH - ep.pixel_y;

                return (
                  <line
                    key={`track_line_${idx}`}
                    x1={sx1}
                    y1={sy1}
                    x2={sx2}
                    y2={sy2}
                    stroke="#22d3ee"
                    strokeWidth={2}
                    strokeDasharray="4,3"
                  />
                );
              })}
            </g>
          )}

          {/* 3. Prediction Vector & Trajectory (When available) */}
          {predictionData?.trajectory_points?.length > 1 && (
            <g className="pointer-events-none">
              {/* Prediction dashed trajectory */}
              {predictionData.trajectory_points.map((pt, idx) => {
                if (idx === 0) return null;
                // Project predicted celestial coordinates to pixel space if WCS present
                if (!observation.wcs?.has_wcs || !observation.wcs.crval || !observation.wcs.crpix) return null;
                const degPerPix = (observation.wcs.pixel_scale_arcsec || 6.2) / 3600;
                const cosDec = Math.cos((observation.wcs.crval[1] * Math.PI) / 180) || 1;

                const dx = -(pt.ra_deg - observation.wcs.crval[0]) * cosDec / degPerPix;
                const dy = (pt.dec_deg - observation.wcs.crval[1]) / degPerPix;
                const px = observation.wcs.crpix[0] + dx;
                const py = imgH - (observation.wcs.crpix[1] + dy);

                return (
                  <circle
                    key={`pred_pt_${idx}`}
                    cx={px}
                    cy={py}
                    r={3}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    strokeDasharray="2,2"
                  />
                );
              })}
            </g>
          )}

          {/* 4. Detected Sources Overlay */}
          {overlaySettings.showSources &&
            sources.map((src) => {
              const screenX = src.pixel_x;
              const screenY = imgH - src.pixel_y;
              const isSelected = src.id === selectedSource?.id;

              return (
                <g
                  key={src.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectSource(src);
                  }}
                  className="cursor-pointer group pointer-events-auto"
                >
                  {/* Positional Uncertainty Ellipse (When enabled) */}
                  {overlaySettings.showUncertainty && (
                    <circle
                      cx={screenX}
                      cy={screenY}
                      r={Math.max(12, (src.position_uncertainty_arcsec || 0.5) * 8)}
                      fill="none"
                      stroke={isSelected ? "rgba(34, 211, 238, 0.4)" : "rgba(255, 255, 255, 0.2)"}
                      strokeWidth={1}
                      strokeDasharray="2,2"
                    />
                  )}

                  {/* Outer reticle circle */}
                  <circle
                    cx={screenX}
                    cy={screenY}
                    r={isSelected ? 16 : 8}
                    fill={isSelected ? "rgba(6, 182, 212, 0.25)" : "none"}
                    stroke={isSelected ? "#22d3ee" : "rgba(34, 211, 238, 0.7)"}
                    strokeWidth={isSelected ? 2 : 1.2}
                  />

                  {/* Reticle Crosshairs */}
                  {isSelected && (
                    <>
                      <line x1={screenX - 22} y1={screenY} x2={screenX - 8} y2={screenY} stroke="#22d3ee" strokeWidth={1.5} />
                      <line x1={screenX + 8} y1={screenY} x2={screenX + 22} y2={screenY} stroke="#22d3ee" strokeWidth={1.5} />
                      <line x1={screenX} y1={screenY - 22} x2={screenX} y2={screenY - 8} stroke="#22d3ee" strokeWidth={1.5} />
                      <line x1={screenX} y1={screenY + 8} x2={screenX} y2={screenY + 22} stroke="#22d3ee" strokeWidth={1.5} />
                    </>
                  )}

                  {/* Center dot */}
                  <circle cx={screenX} cy={screenY} r={isSelected ? 2.5 : 1.5} fill="#38bdf8" />

                  {/* Source Label (When enabled) */}
                  {(overlaySettings.showLabels || isSelected) && (
                    <text
                      x={screenX + 12}
                      y={screenY - 8}
                      fill="#e2e8f0"
                      fontSize={11}
                      fontFamily="monospace"
                      className="pointer-events-none drop-shadow-md select-none font-bold"
                    >
                      {src.id}
                    </text>
                  )}
                </g>
              );
            })}
        </svg>
      </div>

      {/* Floating Bottom-Left Coordinate & Pixel Readout */}
      <div className="absolute bottom-16 left-3 stellarium-glass rounded-full px-3 py-1 pointer-events-none text-[11px] font-mono text-slate-300 flex items-center space-x-3 shadow-lg">
        {cursorPos ? (
          <>
            <div>
              <span className="text-slate-500">Pix: </span>
              <span className="text-white font-bold">
                X:{cursorPos.px.toFixed(1)} Y:{cursorPos.py.toFixed(1)}
              </span>
            </div>
            {cursorPos.ra !== null && cursorPos.dec !== null && (
              <div className="border-l border-white/10 pl-2">
                <span className="text-slate-500">J2000: </span>
                <span className="text-cyan-400 font-bold">
                  RA {cursorPos.ra.toFixed(4)}°, Dec {cursorPos.dec.toFixed(4)}°
                </span>
              </div>
            )}
          </>
        ) : (
          <span className="text-slate-500 italic">Pointer in focal plane</span>
        )}
      </div>

      {/* Floating Zoom & Fit Controls (Right side) */}
      <div className="absolute right-3 top-16 flex flex-col space-y-1.5 pointer-events-auto select-none">
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
