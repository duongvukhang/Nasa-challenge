import React, { useState } from "react";
import {
  Crosshair,
  Search,
  Trash2,
  Maximize2,
  Activity,
  Compass,
  X,
  ChevronRight,
  Sparkles,
  ShieldAlert
} from "lucide-react";

export const SelectedObjectManager = ({
  selectedSource,
  observation,
  activeTrack,
  onInspect,
  onDelete,
  onCenter,
  onTrack,
  onOpenSpectrum,
  onDeselect
}) => {
  const [showConfirm, setShowConfirm] = useState(false);

  if (!selectedSource) return null;

  return (
    <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-35 pointer-events-auto select-none font-mono animate-fadeIn">
      <div className="stellarium-glass-dark border border-cyan-500/40 rounded-2xl p-2 px-3 shadow-2xl flex items-center space-x-3 text-xs">
        
        {/* Object Badge & Info */}
        <div className="flex items-center space-x-2 pr-3 border-r border-white/10">
          <div className="w-7 h-7 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-300 shadow-cyan-glow">
            <Crosshair className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-white tracking-wide">{selectedSource.id}</span>
              {activeTrack && (
                <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {activeTrack.track_id}
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-400 font-sans flex items-center space-x-2">
              <span>
                RA {selectedSource.ra_deg != null ? selectedSource.ra_deg.toFixed(4) : "—"}°, Dec{" "}
                {selectedSource.dec_deg != null ? selectedSource.dec_deg.toFixed(4) : "—"}°
              </span>
              {selectedSource.snr != null && (
                <span className="text-cyan-400 font-mono">
                  SNR {selectedSource.snr.toFixed(1)}σ
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        {!showConfirm ? (
          <div className="flex items-center space-x-1 font-sans">
            {/* 1. Inspect Object */}
            <button
              onClick={onInspect}
              className="px-2.5 py-1.5 rounded-xl bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/50 text-cyan-200 transition-all flex items-center space-x-1.5 text-xs font-medium shadow-cyan-glow/20"
              title="Open Comprehensive Object Inspector"
            >
              <Search className="w-3.5 h-3.5 text-cyan-400" />
              <span>Inspect</span>
            </button>

            {/* 2. Center in Viewport */}
            {onCenter && (
              <button
                onClick={() => onCenter(selectedSource)}
                className="p-1.5 rounded-xl hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
                title="Center object in focal plane"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            )}

            {/* 3. Multi-Epoch Track */}
            {onTrack && (
              <button
                onClick={() => onTrack(selectedSource)}
                className="p-1.5 rounded-xl hover:bg-white/10 text-slate-300 hover:text-cyan-300 transition-colors"
                title="Track object across observation epochs"
              >
                <Compass className="w-4 h-4" />
              </button>
            )}

            {/* 4. Spectrum */}
            {onOpenSpectrum && (
              <button
                onClick={onOpenSpectrum}
                className="p-1.5 rounded-xl hover:bg-white/10 text-slate-300 hover:text-amber-300 transition-colors"
                title="View infrared spectrum"
              >
                <Activity className="w-4 h-4" />
              </button>
            )}

            {/* 5. Delete Object Button */}
            <button
              onClick={() => setShowConfirm(true)}
              className="px-2 py-1.5 rounded-xl hover:bg-red-950/70 border border-transparent hover:border-red-500/40 text-slate-400 hover:text-red-300 transition-colors flex items-center space-x-1 text-xs"
              title="Delete object from catalog"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Delete</span>
            </button>

            {/* 6. Deselect */}
            <button
              onClick={onDeselect}
              className="p-1.5 rounded-xl hover:bg-white/10 text-slate-500 hover:text-slate-300 transition-colors ml-1"
              title="Deselect object"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          /* Confirm Delete View */
          <div className="flex items-center space-x-2 font-sans text-xs bg-red-950/80 px-2.5 py-1 rounded-xl border border-red-500/50 text-red-200">
            <ShieldAlert className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
            <span>Delete {selectedSource.id}?</span>
            <button
              onClick={() => {
                onDelete(selectedSource.id);
                setShowConfirm(false);
              }}
              className="px-2 py-0.5 rounded bg-red-600 hover:bg-red-500 text-white font-bold text-[11px] transition-colors"
            >
              Yes
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
            >
              Cancel
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
