import React from "react";
import {
  Crosshair,
  Tag,
  Grid3X3,
  Compass,
  Disc,
  Activity,
  Clock,
  Sliders,
  Layers
} from "lucide-react";

export const BottomDock = ({
  overlaySettings = {},
  onToggleOverlay,
  isSpectrumOpen,
  onToggleSpectrum,
  isTimelineVisible,
  onToggleTimeline,
  isSettingsOpen,
  onToggleSettings,
  isTrackListOpen,
  onToggleTrackList,
  tracksCount = 0
}) => {
  const tools = [
    {
      id: "showSources",
      label: "Source Reticles",
      icon: Crosshair,
      active: overlaySettings.showSources,
      onClick: () => onToggleOverlay("showSources")
    },
    {
      id: "showLabels",
      label: "Source Labels",
      icon: Tag,
      active: overlaySettings.showLabels,
      onClick: () => onToggleOverlay("showLabels")
    },
    {
      id: "showGrid",
      label: "Celestial Coordinate Grid",
      icon: Grid3X3,
      active: overlaySettings.showGrid,
      onClick: () => onToggleOverlay("showGrid")
    },
    {
      id: "showTrajectories",
      label: "Multi-Epoch Tracking Trajectories",
      icon: Compass,
      active: overlaySettings.showTrajectories,
      onClick: () => onToggleOverlay("showTrajectories")
    },
    {
      id: "tracksList",
      label: `Active Multi-Epoch Tracks (${tracksCount})`,
      icon: Layers,
      active: isTrackListOpen,
      onClick: onToggleTrackList
    },
    {
      id: "showUncertainty",
      label: "Positional Uncertainty Ellipses",
      icon: Disc,
      active: overlaySettings.showUncertainty,
      onClick: () => onToggleOverlay("showUncertainty")
    },
    {
      id: "spectrum",
      label: "Infrared LVF Spectral Mode",
      icon: Activity,
      active: isSpectrumOpen,
      onClick: onToggleSpectrum
    },
    {
      id: "timeline",
      label: "Observation Epoch Controls",
      icon: Clock,
      active: isTimelineVisible,
      onClick: onToggleTimeline
    },
    {
      id: "sliders",
      label: "Contrast & Brightness Controls",
      icon: Sliders,
      active: isSettingsOpen,
      onClick: onToggleSettings
    }
  ];

  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-30 pointer-events-auto select-none">
      <div className="stellarium-glass rounded-full px-2 py-1.5 flex items-center space-x-1 shadow-2xl">
        {tools.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={t.onClick}
              className={`p-2 rounded-full transition-all relative group ${
                t.active
                  ? "bg-cyan-500/25 text-cyan-300 border border-cyan-400/50 shadow-cyan-glow"
                  : "text-slate-400 hover:text-white hover:bg-white/10"
              }`}
              title={t.label}
            >
              <Icon className="w-4 h-4" />
              {/* Active pip */}
              {t.active && (
                <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-cyan-400" />
              )}

              {/* Stellarium hover tooltip badge */}
              <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-black/85 text-slate-200 border border-white/10 px-2 py-0.5 rounded text-[10px] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity shadow-lg">
                {t.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
