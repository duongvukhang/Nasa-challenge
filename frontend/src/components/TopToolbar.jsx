import React, { useState, useRef, useEffect } from "react";
import {
  Menu,
  Search,
  Telescope,
  Maximize,
  Minimize,
  Sliders,
  Calendar,
  Crosshair,
  Sparkles,
  CheckCircle2,
  X
} from "lucide-react";

export const TopToolbar = ({
  currentObservation,
  sources = [],
  selectedSource,
  onSelectSource,
  onSearchCoordinates,
  isSidebarOpen,
  onToggleSidebar,
  isSettingsOpen,
  onToggleSettings,
  isFullscreen,
  onToggleFullscreen
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const searchRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter sources matching query
  const q = searchQuery.trim().toLowerCase();
  const matchedSources = q
    ? sources.filter((s) => s.id.toLowerCase().includes(q)).slice(0, 8)
    : [];

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!q) return;

    // Check if query is in "RA, Dec" format e.g. "276.26, 64.82" or "276.26 64.82"
    const coordMatch = q.match(/^([+-]?\d+(?:\.\d+)?)[,\s]+([+-]?\d+(?:\.\d+)?)$/);
    if (coordMatch) {
      const ra = parseFloat(coordMatch[1]);
      const dec = parseFloat(coordMatch[2]);
      if (ra >= 0 && ra <= 360 && dec >= -90 && dec <= 90) {
        onSearchCoordinates(ra, dec);
        setIsDropdownOpen(false);
        return;
      }
    }

    // Otherwise select first matched source
    if (matchedSources.length > 0) {
      onSelectSource(matchedSources[0]);
      setIsDropdownOpen(false);
    }
  };

  // Calculate approximate Field of View (FOV)
  let fovString = null;
  if (currentObservation?.wcs?.pixel_scale_arcsec && currentObservation?.image_shape) {
    const [h, w] = currentObservation.image_shape;
    const fovWidthDeg = (w * currentObservation.wcs.pixel_scale_arcsec) / 3600;
    const fovHeightDeg = (h * currentObservation.wcs.pixel_scale_arcsec) / 3600;
    if (fovWidthDeg >= 1.0) {
      fovString = `${fovWidthDeg.toFixed(1)}° × ${fovHeightDeg.toFixed(1)}°`;
    } else {
      fovString = `${(fovWidthDeg * 60).toFixed(1)}′ × ${(fovHeightDeg * 60).toFixed(1)}′`;
    }
  }

  return (
    <header className="absolute top-2.5 inset-x-3 z-30 flex items-center justify-between pointer-events-none select-none">
      {/* Left Pill: Menu & SkyTrace Brand */}
      <div className="flex items-center space-x-2 stellarium-glass rounded-full px-3 py-1.5 pointer-events-auto shadow-lg text-xs">
        <button
          onClick={onToggleSidebar}
          className={`p-1 rounded-full transition-colors ${
            isSidebarOpen
              ? "bg-cyan-500/30 text-cyan-300"
              : "hover:bg-white/10 text-slate-300 hover:text-white"
          }`}
          title="Toggle Stellarium Navigation Panel"
        >
          <Menu className="w-4 h-4" />
        </button>

        <div className="flex items-center space-x-1.5 pr-1">
          <Telescope className="w-4 h-4 text-cyan-400" />
          <span className="font-bold tracking-wider uppercase text-[12px] text-white">
            SkyTrace
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 hidden sm:inline">
            SPHEREx
          </span>
        </div>

        {/* Data Source Beacon */}
        {currentObservation && (
          <div className="hidden md:flex items-center space-x-1 pl-1 border-l border-white/10">
            {currentObservation.is_synthetic_demo ? (
              <span className="flex items-center space-x-1 text-[10px] font-mono text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                <span>DEMO</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 text-[10px] font-mono text-cyan-400">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span>REAL SPHEREx</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Center: Stellarium-Style Search Omnibox */}
      <div ref={searchRef} className="relative pointer-events-auto max-w-sm w-full mx-2 hidden sm:block">
        <form onSubmit={handleSearchSubmit} className="relative">
          <div className="stellarium-glass rounded-full flex items-center px-3 py-1 shadow-lg border border-white/10 focus-within:border-cyan-500/60 focus-within:shadow-cyan-glow transition-all">
            <Search className="w-3.5 h-3.5 text-slate-400 mr-2 flex-shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsDropdownOpen(true);
              }}
              onFocus={() => setIsDropdownOpen(true)}
              placeholder="Search source (src_001) or RA, Dec (276.26, 64.82)..."
              className="bg-transparent text-xs text-white placeholder-slate-400 focus:outline-none w-full font-mono"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-slate-400 hover:text-white p-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </form>

        {/* Autocomplete Dropdown */}
        {isDropdownOpen && searchQuery && (
          <div className="absolute top-10 inset-x-0 stellarium-glass-dark rounded-xl p-2 shadow-2xl border border-white/10 text-xs font-mono max-h-60 overflow-y-auto z-40 space-y-1">
            {matchedSources.length > 0 ? (
              matchedSources.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    onSelectSource(s);
                    setIsDropdownOpen(false);
                    setSearchQuery(s.id);
                  }}
                  className="w-full text-left p-1.5 rounded hover:bg-cyan-950/60 hover:text-cyan-300 flex items-center justify-between text-slate-300 transition-colors"
                >
                  <div className="flex items-center space-x-1.5">
                    <Crosshair className="w-3 h-3 text-cyan-400" />
                    <span className="font-bold">{s.id}</span>
                  </div>
                  <span className="text-[10px] text-slate-400">
                    {s.ra_deg?.toFixed(3)}°, {s.dec_deg?.toFixed(3)}°
                  </span>
                </button>
              ))
            ) : (
              <div className="p-2 text-slate-400 text-[11px] text-center">
                Press Enter to search coordinates: <span className="text-cyan-400">{searchQuery}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Pill: FOV, Date, Settings, Fullscreen */}
      <div className="flex items-center space-x-2 stellarium-glass rounded-full px-3 py-1.5 pointer-events-auto shadow-lg text-xs font-mono text-slate-300">
        {fovString && (
          <span className="text-[11px] text-cyan-400 hidden lg:inline" title="Current Field of View">
            FOV {fovString}
          </span>
        )}

        {currentObservation?.date_obs && (
          <div className="flex items-center space-x-1 text-[11px] text-slate-300 border-l border-white/10 pl-2">
            <Calendar className="w-3 h-3 text-cyan-400" />
            <span className="hidden sm:inline">{currentObservation.date_obs.slice(0, 10)}</span>
          </div>
        )}

        <button
          onClick={onToggleSettings}
          className={`p-1 rounded-full transition-colors ${
            isSettingsOpen
              ? "bg-cyan-500/30 text-cyan-300"
              : "hover:bg-white/10 text-slate-300 hover:text-white"
          }`}
          title="Quick Image Display Controls"
        >
          <Sliders className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={onToggleFullscreen}
          className="p-1 rounded-full hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
          title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
        >
          {isFullscreen ? <Minimize className="w-3.5 h-3.5" /> : <Maximize className="w-3.5 h-3.5" />}
        </button>
      </div>
    </header>
  );
};
