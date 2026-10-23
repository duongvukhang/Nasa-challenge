import React, { useState, useRef, useEffect } from "react";
import {
  Compass,
  Sliders,
  Calendar,
  Info,
  Database,
  Upload,
  Layers,
  Crosshair,
  Grid3X3,
  Tag,
  Disc,
  X,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  ExternalLink,
  Search,
  Trash2
} from "lucide-react";

export const Sidebar = ({
  isOpen,
  onClose,
  observations = [],
  activeObservationId,
  onSelectObservation,
  onDeleteObservation,
  onClearSession,
  sources = [],
  selectedSource,
  onSelectSource,
  onUploadFits,
  onLoadDemo,
  onLoadRealSample,
  onOpenArchiveModal,
  onOpenHowItWorks,
  displaySettings,
  onChangeDisplaySettings,
  overlaySettings,
  onToggleOverlay,
  onSearchCoordinates
}) => {
  const [activeTab, setActiveTab] = useState("explore"); // 'explore' | 'display' | 'observations' | 'info'
  const fileInputRef = useRef(null);

  // Form inputs for coordinate query
  const [raInput, setRaInput] = useState("276.26");
  const [decInput, setDecInput] = useState("64.82");

  const activeObs = observations.find((o) => o.observation_id === activeObservationId);

  // Automatically synchronize search inputs with the active observation celestial center
  useEffect(() => {
    if (activeObs?.wcs?.has_wcs && activeObs.wcs.crval) {
      setRaInput(activeObs.wcs.crval[0].toFixed(4));
      setDecInput(activeObs.wcs.crval[1].toFixed(4));
    }
  }, [activeObs?.observation_id]);

  const handleCoordinateSubmit = (e) => {
    e.preventDefault();
    const ra = parseFloat(raInput);
    const dec = parseFloat(decInput);
    if (!isNaN(ra) && !isNaN(dec)) {
      onSearchCoordinates(ra, dec);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadFits(e.target.files[0]);
    }
  };

  return (
    <>
      {/* Backdrop overlay on smaller screens */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-30 lg:hidden"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 flex transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Vertical Icon Strip (Stellarium-style left strip) */}
        <div className="w-13 bg-space-950/95 border-r border-white/10 flex flex-col items-center py-4 space-y-4 text-slate-400 select-none">
          <button
            onClick={() => setActiveTab("explore")}
            className={`p-2.5 rounded-xl transition-all ${
              activeTab === "explore"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-cyan-glow"
                : "hover:bg-white/10 hover:text-white"
            }`}
            title="Explore Data & Sources"
          >
            <Compass className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveTab("display")}
            className={`p-2.5 rounded-xl transition-all ${
              activeTab === "display"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-cyan-glow"
                : "hover:bg-white/10 hover:text-white"
            }`}
            title="View Settings & Overlays"
          >
            <Sliders className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveTab("observations")}
            className={`p-2.5 rounded-xl transition-all ${
              activeTab === "observations"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-cyan-glow"
                : "hover:bg-white/10 hover:text-white"
            }`}
            title="Observation Epochs & Metadata"
          >
            <Calendar className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveTab("info")}
            className={`p-2.5 rounded-xl transition-all ${
              activeTab === "info"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-cyan-glow"
                : "hover:bg-white/10 hover:text-white"
            }`}
            title="Mission Guide & Scientific Methodology"
          >
            <Info className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Content Area */}
        <div className="w-80 sm:w-88 stellarium-glass-dark border-r border-white/10 flex flex-col h-full text-xs text-slate-300 select-none shadow-2xl">
          {/* Drawer Header */}
          <div className="p-3.5 border-b border-white/10 flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-white">
              {activeTab === "explore" && "Explore Data"}
              {activeTab === "display" && "View Settings"}
              {activeTab === "observations" && "Observations"}
              {activeTab === "info" && "Information"}
            </span>
            <button
              onClick={onClose}
              className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* TAB 1: EXPLORE DATA */}
            {activeTab === "explore" && (
              <div className="space-y-4">
                {/* Data Load Triggers */}
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-2">
                    Data Acquisition
                  </span>
                  <div className="grid grid-cols-2 gap-2 font-mono">
                    <button
                      onClick={onLoadRealSample}
                      className="p-2.5 rounded-lg bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-800/60 text-cyan-200 text-left transition-colors space-y-1"
                    >
                      <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                      <div className="font-bold text-[11px]">Load Real SPHEREx</div>
                      <div className="text-[9px] text-slate-400 font-sans">Level 2 calibrated image</div>
                    </button>

                    <button
                      onClick={onLoadDemo}
                      className="p-2.5 rounded-lg bg-amber-950/30 hover:bg-amber-900/40 border border-amber-800/60 text-amber-200 text-left transition-colors space-y-1"
                    >
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <div className="font-bold text-[11px]">Load Demo</div>
                      <div className="text-[9px] text-slate-400 font-sans">3-epoch simulated field</div>
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-2 font-mono">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 text-center transition-colors flex items-center justify-center space-x-1.5"
                    >
                      <Upload className="w-3.5 h-3.5 text-slate-400" />
                      <span>Upload FITS</span>
                    </button>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept=".fits,.fit,.fits.gz"
                      className="hidden"
                    />

                    <button
                      onClick={onOpenArchiveModal}
                      className="p-2 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 border border-cyan-700/60 text-cyan-300 text-center transition-colors flex items-center justify-center space-x-1.5"
                    >
                      <Database className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Search IRSA</span>
                    </button>
                  </div>
                </div>

                {/* Sky Coordinate Jump */}
                <div className="pt-2 border-t border-white/10">
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-2">
                    Coordinate Cone Search
                  </span>
                  <form onSubmit={handleCoordinateSubmit} className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 font-mono">
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">RA (deg)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={raInput}
                          onChange={(e) => setRaInput(e.target.value)}
                          className="w-full bg-black/40 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">Dec (deg)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={decInput}
                          onChange={(e) => setDecInput(e.target.value)}
                          className="w-full bg-black/40 border border-white/10 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-cyan-500"
                        />
                      </div>
                    </div>
                    <button
                      type="submit"
                      className="w-full py-1.5 rounded bg-white/5 hover:bg-cyan-950 text-slate-200 hover:text-cyan-300 border border-white/10 hover:border-cyan-700 transition-colors flex items-center justify-center space-x-1.5 text-xs"
                    >
                      <Search className="w-3.5 h-3.5" />
                      <span>Query Archive at Location</span>
                    </button>
                  </form>
                </div>

                {/* Detected Sources List */}
                <div className="pt-2 border-t border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                      Detected Sources ({sources.length})
                    </span>
                    <span className="text-[9px] font-mono text-cyan-400">DAOStarFinder</span>
                  </div>

                  {sources.length === 0 ? (
                    <div className="p-3 rounded bg-black/40 text-center text-slate-500 text-[11px]">
                      No sources detected in active field.
                    </div>
                  ) : (
                    <div className="max-h-48 overflow-y-auto space-y-1 pr-1 font-mono text-[11px]">
                      {sources.map((src) => {
                        const isSelected = src.id === selectedSource?.id;
                        return (
                          <button
                            key={src.id}
                            onClick={() => onSelectSource(src)}
                            className={`w-full text-left p-2 rounded transition-colors flex items-center justify-between border ${
                              isSelected
                                ? "bg-cyan-950/60 border-cyan-500/60 text-cyan-200 shadow-sm"
                                : "bg-black/30 border-white/5 hover:bg-white/5 text-slate-300"
                            }`}
                          >
                            <div className="flex items-center space-x-2">
                              <Crosshair className="w-3 h-3 text-cyan-400" />
                              <span className="font-bold">{src.id}</span>
                            </div>
                            <div className="text-[10px] text-slate-400">
                              {src.peak_flux.toFixed(1)} {src.flux_unit}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: VIEW SETTINGS & OVERLAYS */}
            {activeTab === "display" && (
              <div className="space-y-4">
                {/* Overlays Checklist */}
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-2">
                    Observational Overlays
                  </span>
                  <div className="space-y-1.5">
                    {[
                      { key: "showSources", label: "Source Detection Reticles", icon: Crosshair },
                      { key: "showLabels", label: "Source Identity Labels", icon: Tag },
                      { key: "showGrid", label: "Celestial Coordinate Grid (RA/Dec)", icon: Grid3X3 },
                      { key: "showTrajectories", label: "Multi-Epoch Tracking Trajectories", icon: Compass },
                      { key: "showUncertainty", label: "Positional Uncertainty Ellipses", icon: Disc },
                    ].map((item) => {
                      const Icon = item.icon;
                      const active = overlaySettings[item.key];
                      return (
                        <button
                          key={item.key}
                          onClick={() => onToggleOverlay(item.key)}
                          className={`w-full p-2 rounded-lg border text-left flex items-center justify-between transition-colors ${
                            active
                              ? "bg-cyan-950/50 border-cyan-500/60 text-cyan-200"
                              : "bg-black/30 border-white/5 text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          <div className="flex items-center space-x-2">
                            <Icon className={`w-3.5 h-3.5 ${active ? "text-cyan-400" : "text-slate-500"}`} />
                            <span className="text-[11px]">{item.label}</span>
                          </div>
                          <span className={`text-[10px] font-mono ${active ? "text-cyan-400 font-bold" : "text-slate-600"}`}>
                            {active ? "ON" : "OFF"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Display Scaling Controls */}
                <div className="pt-2 border-t border-white/10 space-y-3">
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                    FITS Visualization Scaling
                  </span>

                  {/* Stretch selection */}
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Astronomical Stretch</label>
                    <div className="grid grid-cols-4 gap-1 font-mono text-[10px]">
                      {["asinh", "linear", "log", "sqrt"].map((st) => (
                        <button
                          key={st}
                          onClick={() => onChangeDisplaySettings({ stretch: st })}
                          className={`py-1 rounded border uppercase text-center transition-colors ${
                            displaySettings.stretch === st
                              ? "bg-cyan-950 border-cyan-500 text-cyan-300 font-bold"
                              : "bg-black/40 border-white/5 text-slate-400 hover:text-white"
                          }`}
                        >
                          {st}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Colormap */}
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Color Palette</label>
                    <select
                      value={displaySettings.colormap}
                      onChange={(e) => onChangeDisplaySettings({ colormap: e.target.value })}
                      className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                    >
                      <option value="inferno">Inferno (Infrared Standard)</option>
                      <option value="viridis">Viridis</option>
                      <option value="plasma">Plasma</option>
                      <option value="gray">Grayscale</option>
                      <option value="magma">Magma</option>
                    </select>
                  </div>

                  {/* Brightness & Contrast */}
                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                        <span>Brightness</span>
                        <span className="font-mono text-white">{displaySettings.brightness.toFixed(2)}x</span>
                      </div>
                      <input
                        type="range"
                        min="0.4"
                        max="2.5"
                        step="0.1"
                        value={displaySettings.brightness}
                        onChange={(e) => onChangeDisplaySettings({ brightness: parseFloat(e.target.value) })}
                        className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                        <span>Contrast</span>
                        <span className="font-mono text-white">{displaySettings.contrast.toFixed(2)}x</span>
                      </div>
                      <input
                        type="range"
                        min="0.4"
                        max="2.5"
                        step="0.1"
                        value={displaySettings.contrast}
                        onChange={(e) => onChangeDisplaySettings({ contrast: parseFloat(e.target.value) })}
                        className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: OBSERVATIONS */}
            {activeTab === "observations" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                    Loaded Observations ({observations.length})
                  </span>
                  {observations.length > 0 && onClearSession && (
                    <button
                      onClick={onClearSession}
                      className="text-[10px] text-red-400 hover:text-red-300 flex items-center space-x-1 transition-colors"
                      title="Clear all observations from active session"
                    >
                      <Trash2 className="w-3 h-3" />
                      <span>Clear All</span>
                    </button>
                  )}
                </div>

                <div className="space-y-1.5">
                  {observations.map((obs) => {
                    const isActive = obs.observation_id === activeObservationId;
                    return (
                      <div
                        key={obs.observation_id}
                        onClick={() => onSelectObservation(obs.observation_id)}
                        className={`w-full text-left p-2.5 rounded-lg border transition-colors cursor-pointer group ${
                          isActive
                            ? "bg-cyan-950/60 border-cyan-500 text-cyan-100 shadow-sm"
                            : "bg-black/30 border-white/5 hover:bg-white/5 text-slate-300"
                        }`}
                      >
                        <div className="flex justify-between items-center font-mono text-[11px] mb-1">
                          <span className="font-bold truncate max-w-[150px]" title={obs.filename}>
                            {obs.filename}
                          </span>
                          <div className="flex items-center space-x-1.5">
                            <span className={`text-[9px] px-1.5 py-0.2 rounded ${
                              obs.is_synthetic_demo
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-cyan-950 text-cyan-400 border border-cyan-800"
                            }`}>
                              {obs.is_synthetic_demo ? "DEMO" : "REAL"}
                            </span>
                            {onDeleteObservation && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onDeleteObservation(obs.observation_id);
                                }}
                                className="p-1 rounded opacity-60 hover:opacity-100 text-slate-400 hover:text-red-400 hover:bg-red-950/50 transition-all"
                                title="Remove this observation"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono flex justify-between">
                          <span>{obs.band || "LVF"} • {obs.bunit}</span>
                          <span>{obs.date_obs ? obs.date_obs.slice(0, 10) : "Undated"}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {activeObs && (
                  <div className="pt-2 border-t border-white/10 space-y-1.5 font-mono text-[10px] text-slate-400">
                    <span className="text-white font-bold block">Active FITS Metadata:</span>
                    <div className="flex justify-between">
                      <span>Telescope:</span>
                      <span className="text-white">{activeObs.telescope}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Dimensions:</span>
                      <span className="text-white">{activeObs.image_shape?.join(" × ")} px</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Pixel Scale:</span>
                      <span className="text-white">{activeObs.wcs?.pixel_scale_arcsec?.toFixed(2)}″ / px</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Science HDU:</span>
                      <span className="text-cyan-400">{activeObs.science_hdu_name}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: INFORMATION */}
            {activeTab === "info" && (
              <div className="space-y-3 leading-relaxed text-slate-300 text-xs">
                <div className="p-3 rounded-lg bg-black/40 border border-white/10 space-y-1.5">
                  <span className="font-bold text-cyan-400 block text-xs">NASA SPHEREx Mission</span>
                  <p className="text-[11px] text-slate-400">
                    SPHEREx performs an all-sky spectral survey across 102 infrared channels (0.75 to 5.0 µm) utilizing Linear Variable Filters (LVF).
                  </p>
                </div>

                <div className="space-y-1.5 text-[11px]">
                  <button
                    onClick={onOpenHowItWorks}
                    className="w-full p-2.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-left flex items-center justify-between text-white transition-colors"
                  >
                    <span>Scientific Methodology & Transparency</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                </div>

                <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-800/40 text-[10px] text-amber-200/80">
                  <strong className="block text-amber-300 mb-0.5">Scientific Transparency:</strong>
                  SkyTrace does not claim to discover Planet X. Point detections represent photometric peaks above background noise, requiring multi-epoch orbital arc validation.
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
