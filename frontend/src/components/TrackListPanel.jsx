import React from "react";
import {
  X,
  Compass,
  Eye,
  EyeOff,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Activity,
  Layers
} from "lucide-react";
import { getStableTrackColor } from "../utils/colors";

export const TrackListPanel = ({
  isOpen,
  onClose,
  tracks = {},
  activeTrackId,
  onSelectTrack,
  onInspectTrack,
  onOpenSkyPlot,
  onDeleteTrack,
  onClearTracks,
  hiddenTrackIds = new Set(),
  onToggleTrackVisibility
}) => {
  if (!isOpen) return null;

  const trackList = Object.values(tracks);

  const renderStatusBadge = (status) => {
    switch (status) {
      case "STRONG MATCH":
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" />
            <span>STRONG</span>
          </span>
        );
      case "REVIEW NEEDED":
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3" />
            <span>REVIEW</span>
          </span>
        );
      case "AMBIGUOUS":
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
            <AlertCircle className="w-3 h-3" />
            <span>AMBIGUOUS</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-500/20 text-slate-300 border border-slate-500/30">
            <HelpCircle className="w-3 h-3" />
            <span>INSUFFICIENT</span>
          </span>
        );
    }
  };

  return (
    <div className="absolute top-16 left-16 z-40 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark border border-white/15 rounded-2xl w-80 sm:w-96 max-h-[80vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        
        {/* Header */}
        <div className="p-3.5 border-b border-white/10 flex items-center justify-between bg-black/40">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <span className="font-bold text-white text-xs block">Active Multi-Epoch Tracks</span>
              <span className="text-[10px] text-slate-400 font-sans">
                {trackList.length} track{trackList.length === 1 ? "" : "s"} tracked across epochs
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            {trackList.length > 0 && onClearTracks && (
              <button
                onClick={() => {
                  if (confirm("Clear all active tracks?")) onClearTracks();
                }}
                className="p-1 rounded hover:bg-red-950/60 text-slate-400 hover:text-red-300 transition-colors"
                title="Clear all tracks"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
              title="Close Panel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Track List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {trackList.length === 0 ? (
            <div className="py-8 px-4 text-center text-slate-400 text-xs font-sans space-y-2">
              <Compass className="w-8 h-8 text-cyan-400/50 mx-auto" />
              <p className="font-medium text-slate-300">No Multi-Epoch Tracks</p>
              <p className="text-[11px] leading-relaxed text-slate-500">
                Click any detected source in the observation image to automatically track its celestial trajectory across all loaded epochs.
              </p>
            </div>
          ) : (
            trackList.map((tr) => {
              const isSelected = tr.track_id === activeTrackId;
              const isHidden = hiddenTrackIds.has(tr.track_id);
              const color = tr.color || getStableTrackColor(tr.track_id);

              return (
                <div
                  key={tr.track_id}
                  onClick={() => onSelectTrack(tr.track_id)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? "bg-cyan-950/30 border-cyan-500/50 shadow-cyan-glow/20"
                      : "bg-black/30 border-white/5 hover:border-white/15 hover:bg-white/5"
                  } ${isHidden ? "opacity-50" : ""}`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center space-x-2">
                      <div
                        className="w-3.5 h-3.5 rounded-full"
                        style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
                      />
                      <span className="font-bold text-white text-xs">{tr.track_id}</span>
                      {renderStatusBadge(tr.quality_status)}
                    </div>

                    <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => onToggleTrackVisibility?.(tr.track_id)}
                        className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                        title={isHidden ? "Show Track Overlay" : "Hide Track Overlay"}
                      >
                        {isHidden ? <EyeOff className="w-3.5 h-3.5 text-slate-500" /> : <Eye className="w-3.5 h-3.5 text-cyan-400" />}
                      </button>
                      <button
                        onClick={() => onOpenSkyPlot?.(tr)}
                        className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-cyan-300 transition-colors"
                        title="View Sky Plot"
                      >
                        <Compass className="w-3.5 h-3.5" />
                      </button>
                      {onDeleteTrack && (
                        <button
                          onClick={() => onDeleteTrack(tr.track_id)}
                          className="p-1 rounded hover:bg-red-950/60 text-slate-500 hover:text-red-300 transition-colors"
                          title="Delete Track"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-400 font-sans">
                    <div>
                      Ref: <span className="text-slate-200 font-mono">{tr.reference_source_id}</span>
                    </div>
                    <div className="text-right">
                      Detections: <span className="text-white font-mono">{tr.detected_epochs_count}/{tr.total_eligible_epochs}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5 text-[10px]">
                    <span className="text-slate-500 truncate max-w-[170px]">
                      {tr.fit_info?.fit_model || "Stationary Source"}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onInspectTrack(tr);
                      }}
                      className="px-2 py-0.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-600/40 text-cyan-300 font-sans font-medium transition-colors"
                    >
                      Inspect Quality →
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

      </div>
    </div>
  );
};
