import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Compass,
} from "lucide-react";
import { api } from "../services/api";
import { getStableTrackColor } from "../utils/colors";

export const SkyViewer = ({
  observation,
  sources = [],
  selectedSource,
  onSelectSource,
  overlaySettings = {},
  displaySettings = {},
  tracks = {},
  activeTrackId = null,
  onSelectTrack = null,
  hiddenTrackIds = new Set(),
  trackData = null,
  predictionData = null,
  centerTarget = null,
  isLoading = false
}) => {
  // Zoom & Pan state
  const [scale, setScale] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  // Center on target when requested
  useEffect(() => {
    if (centerTarget && imgRef.current && observation?.image_shape) {
      const [imgHeight, imgWidth] = observation.image_shape;
      if (centerTarget.pixel_x != null && centerTarget.pixel_y != null) {
        const normOffsetX = (centerTarget.pixel_x - imgWidth / 2) / imgWidth;
        const normOffsetY = (centerTarget.pixel_y - imgHeight / 2) / imgHeight;

        const renderedW = imgRef.current.clientWidth || 800;
        const renderedH = imgRef.current.clientHeight || 800;

        const targetScale = Math.max(scale, 2.5);
        setScale(targetScale);
        setPan({
          x: -normOffsetX * renderedW * targetScale,
          y: normOffsetY * renderedH * targetScale
        });
      }
    }
  }, [centerTarget]);

  // Dynamic cursor celestial coordinate readout
  const [cursorPos, setCursorPos] = useState(null);
  const hoverDebounceRef = useRef(null);
  const [projectedCoordsMap, setProjectedCoordsMap] = useState({});

  // Reset view to center and fit
  const handleResetView = useCallback(() => {
    setScale(1.0);
    setPan({ x: 0, y: 0 });
  }, []);

  const prevObsIdRef = useRef(null);

  // Preserve user zoom and pan during motion simulation and epoch switching.
  // Only auto-reset on initial load or when loading the first observation from empty state.
  useEffect(() => {
    if (!prevObsIdRef.current && observation?.observation_id) {
      handleResetView();
    }
    prevObsIdRef.current = observation?.observation_id || null;
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

        // Debounced exact Astropy WCS readout from backend
        if (observation.wcs?.has_wcs) {
          if (hoverDebounceRef.current) clearTimeout(hoverDebounceRef.current);
          hoverDebounceRef.current = setTimeout(() => {
            api
              .pixelToWorld(observation.observation_id, px, py)
              .then((res) => {
                if (res?.ra_deg != null && res?.dec_deg != null) {
                  setCursorPos((prev) =>
                    prev ? { ...prev, ra: res.ra_deg, dec: res.dec_deg, wavelength_um: res.wavelength_um } : null
                  );
                }
              })
              .catch(() => {});
          }, 150);
        }
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

  // Compile all active tracks (supporting multiple simultaneous tracks)
  const allTrackList = Object.values(tracks).length > 0
    ? Object.values(tracks)
    : (trackData ? [trackData] : []);

  const visibleTrackList = allTrackList.filter((tr) => tr && !hiddenTrackIds.has(tr.track_id));

  // Batch project all celestial coordinates via backend Astropy WCS
  useEffect(() => {
    if (!observation?.observation_id || !observation?.wcs?.has_wcs) return;

    const coordsToProject = [];
    visibleTrackList.forEach((tr) => {
      tr?.timeline?.forEach((ep) => {
        if (ep.ra_deg != null && ep.dec_deg != null) {
          coordsToProject.push({ ra_deg: ep.ra_deg, dec_deg: ep.dec_deg });
        }
      });
    });
    predictionData?.trajectory_points?.forEach((pt) => {
      if (pt.ra_deg != null && pt.dec_deg != null) {
        coordsToProject.push({ ra_deg: pt.ra_deg, dec_deg: pt.dec_deg });
      }
    });

    if (coordsToProject.length === 0) return;

    let isSubscribed = true;
    api
      .projectCoordinates(observation.observation_id, coordsToProject)
      .then((res) => {
        if (!isSubscribed || !res?.projected) return;
        const mapping = {};
        res.projected.forEach((p) => {
          const key = `${p.ra_deg.toFixed(6)},${p.dec_deg.toFixed(6)}`;
          mapping[key] = {
            x: p.pixel_x,
            y: imgH - p.pixel_y,
            inside: p.inside_bounds
          };
        });
        setProjectedCoordsMap((prev) => ({ ...prev, ...mapping }));
      })
      .catch(() => {});

    return () => {
      isSubscribed = false;
    };
  }, [observation?.observation_id, visibleTrackList, predictionData, imgH]);

  // Helper to accurately project celestial coordinates or epoch pixel positions
  // into the CURRENT displayed observation's SVG pixel space.
  const getEpochScreenCoords = (ep) => {
    if (!ep) return null;

    if (ep.ra_deg != null && ep.dec_deg != null) {
      const key = `${ep.ra_deg.toFixed(6)},${ep.dec_deg.toFixed(6)}`;
      if (projectedCoordsMap[key]) {
        return projectedCoordsMap[key];
      }
    }

    if (
      ep.ra_deg != null &&
      ep.dec_deg != null &&
      observation?.wcs?.has_wcs &&
      observation.wcs.crval &&
      observation.wcs.crpix
    ) {
      const degPerPix = (observation.wcs.pixel_scale_arcsec || 6.2) / 3600;
      const cosDec = Math.cos((observation.wcs.crval[1] * Math.PI) / 180) || 1.0;
      const dx = -(ep.ra_deg - observation.wcs.crval[0]) * cosDec / degPerPix;
      const dy = (ep.dec_deg - observation.wcs.crval[1]) / degPerPix;
      const px = observation.wcs.crpix[0] + dx;
      const py = imgH - (observation.wcs.crpix[1] + dy);
      return { x: px, y: py };
    }

    if (ep.pixel_x != null && ep.pixel_y != null) {
      return { x: ep.pixel_x, y: imgH - ep.pixel_y };
    }

    return null;
  };

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
          className="block max-w-[85vw] max-h-[85vh] object-contain shadow-2xl select-none pointer-events-none"
        />

        {/* Scientific Overlays (SVG) — 1:1 pixel overlay over rendered image */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
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

          <defs>
            <marker
              id="trajArrow"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="4"
              markerHeight="4"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#22d3ee" />
            </marker>
            <marker
              id="predArrow"
              viewBox="0 0 10 10"
              refX="6"
              refY="5"
              markerWidth="4"
              markerHeight="4"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f59e0b" />
            </marker>
          </defs>

          {/* 2. Multi-Epoch Tracking Trajectories & Truth-Based Detection Markers */}
          {overlaySettings.showTrajectories && visibleTrackList.map((tr) => {
            const trackColor = tr.color || getStableTrackColor(tr.track_id);
            const isActive = tr.track_id === activeTrackId;

            // Extract measured waypoints reprojected into current field
            const waypoints = (tr.timeline || [])
              .filter((ep) => ep.is_measured)
              .map((ep, idx) => {
                const coords = getEpochScreenCoords(ep);
                if (!coords) return null;
                return {
                  ...ep,
                  epochIdx: idx + 1,
                  screenX: coords.x,
                  screenY: coords.y,
                  isCurrent: ep.observation_id === observation?.observation_id
                };
              })
              .filter(Boolean);

            if (waypoints.length === 0) return null;

            return (
              <g key={`track_overlay_${tr.track_id}`}>
                {/* Connecting trajectory segments across epochs */}
                {waypoints.map((pt, idx) => {
                  if (idx === 0) return null;
                  const prev = waypoints[idx - 1];
                  const isLast = idx === waypoints.length - 1;

                  return (
                    <g key={`traj_seg_${tr.track_id}_${idx}`} className="pointer-events-none">
                      {/* Underlying glow for active track */}
                      {isActive && (
                        <line
                          x1={prev.screenX}
                          y1={prev.screenY}
                          x2={pt.screenX}
                          y2={pt.screenY}
                          stroke={trackColor}
                          strokeWidth={6}
                          strokeOpacity={0.3}
                          vectorEffect="non-scaling-stroke"
                        />
                      )}
                      {/* Crisp trajectory line */}
                      <line
                        x1={prev.screenX}
                        y1={prev.screenY}
                        x2={pt.screenX}
                        y2={pt.screenY}
                        stroke={trackColor}
                        strokeWidth={isActive ? 2.5 : 1.5}
                        strokeDasharray={isActive ? "5,3" : "4,4"}
                        strokeOpacity={isActive ? 1.0 : 0.75}
                        vectorEffect="non-scaling-stroke"
                      />
                    </g>
                  );
                })}

                {/* Waypoint dots for non-current epochs along the trajectory */}
                {waypoints.map((pt) => {
                  if (pt.isCurrent) return null; // Current epoch rendered below with full interactive reticle
                  return (
                    <g key={`traj_wpt_${tr.track_id}_${pt.epochIdx}`} className="pointer-events-none">
                      <circle
                        cx={pt.screenX}
                        cy={pt.screenY}
                        r={isActive ? 3 : 2}
                        fill={trackColor}
                        stroke="#ffffff"
                        strokeWidth={0.8}
                        vectorEffect="non-scaling-stroke"
                      />
                      <text
                        x={pt.screenX + 5}
                        y={pt.screenY - 4}
                        fill={isActive ? trackColor : "#94a3b8"}
                        fontSize={9}
                        fontFamily="monospace"
                        className="select-none drop-shadow"
                      >
                        E{pt.epochIdx}
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })}

          {/* Confirmed Detection Markers in Current Epoch (Truth-Based: Only when is_measured === true) */}
          {visibleTrackList.map((tr) => {
            const trackColor = tr.color || getStableTrackColor(tr.track_id);
            const isActive = tr.track_id === activeTrackId;
            const currentEp = tr.timeline?.find((ep) => ep.observation_id === observation?.observation_id);

            // Strictly do NOT fabricate marker if source is outside FOV or not detected in this epoch
            if (!currentEp || !currentEp.is_measured) return null;

            const coords = getEpochScreenCoords(currentEp);
            if (!coords) return null;

            return (
              <g
                key={`current_detection_${tr.track_id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectTrack?.(tr.track_id);
                }}
                className="cursor-pointer pointer-events-auto"
              >
                {/* Active track glowing halo */}
                {isActive && (
                  <circle
                    cx={coords.x}
                    cy={coords.y}
                    r={16}
                    fill="none"
                    stroke={trackColor}
                    strokeWidth={1.5}
                    strokeDasharray="4,3"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {/* Main reticle */}
                <circle
                  cx={coords.x}
                  cy={coords.y}
                  r={isActive ? 9 : 7}
                  fill={isActive ? `${trackColor}25` : "none"}
                  stroke={trackColor}
                  strokeWidth={isActive ? 2 : 1.5}
                  vectorEffect="non-scaling-stroke"
                />
                {/* Center pip */}
                <circle
                  cx={coords.x}
                  cy={coords.y}
                  r={isActive ? 3.5 : 2.5}
                  fill={isActive ? "#ffffff" : trackColor}
                  stroke={isActive ? trackColor : "#ffffff"}
                  strokeWidth={0.8}
                  vectorEffect="non-scaling-stroke"
                />
                {/* Track label */}
                <text
                  x={coords.x + (isActive ? 14 : 10)}
                  y={coords.y - 4}
                  fill={trackColor}
                  fontSize={isActive ? 11 : 9}
                  fontFamily="monospace"
                  fontWeight={isActive ? "bold" : "normal"}
                  className="pointer-events-none select-none drop-shadow"
                >
                  {tr.track_id}
                </text>
              </g>
            );
          })}

          {/* 3. Prediction Vector & Trajectory (When available) */}
          {predictionData?.trajectory_points?.length > 1 && (
            <g className="pointer-events-none">
              {/* Prediction dashed trajectory in amber */}
              {predictionData.trajectory_points.map((pt, idx) => {
                if (idx === 0) return null;
                const prev = predictionData.trajectory_points[idx - 1];
                const p1 = getEpochScreenCoords({ ra_deg: prev.ra_deg, dec_deg: prev.dec_deg });
                const p2 = getEpochScreenCoords({ ra_deg: pt.ra_deg, dec_deg: pt.dec_deg });
                if (!p1 || !p2) return null;
                const isLast = idx === predictionData.trajectory_points.length - 1;

                return (
                  <g key={`pred_seg_${idx}`}>
                    <line
                      x1={p1.x}
                      y1={p1.y}
                      x2={p2.x}
                      y2={p2.y}
                      stroke="rgba(245, 158, 11, 0.3)"
                      strokeWidth={4}
                      vectorEffect="non-scaling-stroke"
                    />
                    <line
                      x1={p1.x}
                      y1={p1.y}
                      x2={p2.x}
                      y2={p2.y}
                      stroke="#f59e0b"
                      strokeWidth={1.5}
                      strokeDasharray="4,3"
                      vectorEffect="non-scaling-stroke"
                      markerEnd={isLast ? "url(#predArrow)" : undefined}
                    />
                    <circle
                      cx={p2.x}
                      cy={p2.y}
                      r={2.5}
                      fill="#f59e0b"
                      stroke="#ffffff"
                      strokeWidth={1}
                      vectorEffect="non-scaling-stroke"
                    />
                  </g>
                );
              })}
            </g>
          )}

          {/* 4. Detected Sources Overlay — thin green squares only */}
          {overlaySettings.showSources &&
            sources.map((src) => {
              const screenX = src.pixel_x;
              const screenY = imgH - src.pixel_y;
              const isSelected = src.id === selectedSource?.id;
              const size = isSelected ? 18 : 10;
              const half = size / 2;

              return (
                <g
                  key={src.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectSource(src);
                  }}
                  className="cursor-pointer pointer-events-auto"
                >
                  {/* Thin green square — no fill for unselected, faint fill for selected */}
                  <rect
                    x={screenX - half}
                    y={screenY - half}
                    width={size}
                    height={size}
                    fill={isSelected ? "rgba(34, 197, 94, 0.15)" : "none"}
                    stroke={isSelected ? "#4ade80" : "#22c55e"}
                    strokeWidth={isSelected ? 1.5 : 1}
                    vectorEffect="non-scaling-stroke"
                  />

                  {/* Source Label (When enabled or selected) */}
                  {(overlaySettings.showLabels || isSelected) && (
                    <text
                      x={screenX + half + 3}
                      y={screenY - half + 2}
                      fill="#e2e8f0"
                      fontSize={10}
                      fontFamily="monospace"
                      className="pointer-events-none select-none"
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
