import React, { useState } from "react";
import { Sliders, X, RotateCcw, Crosshair, Sparkles } from "lucide-react";

export const DisplaySettingsPopup = ({
  isOpen,
  onClose,
  settings = {},
  onChangeSettings,
  detectionSettings = {},
  onChangeDetectionSettings,
  sourcesCount = 0
}) => {
  const [activeTab, setActiveTab] = useState("detection"); // Default to detection when opened if user wants to change sources

  if (!isOpen) return null;

  return (
    <div className="absolute top-14 right-3 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark rounded-2xl p-3.5 shadow-2xl border border-white/10 text-xs text-slate-300 w-74 space-y-3">
        {/* Header with Tabs */}
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setActiveTab("detection")}
              className={`px-2 py-1 rounded-lg text-[10px] font-sans font-bold uppercase tracking-wider flex items-center space-x-1 transition-all ${
                activeTab === "detection"
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "text-slate-400 hover:text-white hover:bg-white/5 border border-transparent"
              }`}
            >
              <Crosshair className="w-3 h-3 text-emerald-400" />
              <span>Sources ({sourcesCount})</span>
            </button>
            <button
              onClick={() => setActiveTab("display")}
              className={`px-2 py-1 rounded-lg text-[10px] font-sans font-bold uppercase tracking-wider flex items-center space-x-1 transition-all ${
                activeTab === "display"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-white hover:bg-white/5 border border-transparent"
              }`}
            >
              <Sliders className="w-3 h-3 text-cyan-400" />
              <span>Display</span>
            </button>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-white/10 transition-colors"
            title="Close"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Tab 1: Source Detection Settings */}
        {activeTab === "detection" && (
          <div className="space-y-3 font-sans">
            {/* Live Count Status */}
            <div className="flex items-center justify-between text-[11px] bg-black/40 px-2.5 py-1.5 rounded-lg border border-white/5 font-mono">
              <span className="text-slate-400 flex items-center space-x-1">
                <Sparkles className="w-3 h-3 text-emerald-400" />
                <span>Detected in Field:</span>
              </span>
              <span className="text-emerald-400 font-bold">{sourcesCount} stars</span>
            </div>

            {/* Max Sources Slider & Quick Presets */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-300 mb-1">
                <span className="font-medium">Max Candidate Sources</span>
                <span className="font-mono text-emerald-400 font-bold">
                  {detectionSettings.max_sources ?? 500}
                </span>
              </div>
              <input
                type="range"
                min="25"
                max="1500"
                step="25"
                value={detectionSettings.max_sources ?? 500}
                onChange={(e) =>
                  onChangeDetectionSettings?.({ max_sources: parseInt(e.target.value, 10) })
                }
                className="w-full accent-emerald-400 bg-white/10 h-1.5 rounded cursor-pointer"
              />
              {/* Presets */}
              <div className="grid grid-cols-5 gap-1 mt-1.5 text-[9px] font-mono">
                {[50, 150, 500, 1000, 1500].map((val) => (
                  <button
                    key={val}
                    onClick={() => onChangeDetectionSettings?.({ max_sources: val })}
                    className={`py-0.5 rounded border text-center transition-colors ${
                      (detectionSettings.max_sources ?? 500) === val
                        ? "bg-emerald-950 border-emerald-500 text-emerald-300 font-bold"
                        : "bg-black/30 border-white/5 text-slate-400 hover:text-white"
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            {/* Detection Threshold (Sigma) */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-300 mb-1">
                <span className="font-medium">Sensitivity (Threshold σ)</span>
                <span className="font-mono text-cyan-400 font-bold">
                  {(detectionSettings.threshold_sigma ?? 3.5).toFixed(1)} σ
                </span>
              </div>
              <input
                type="range"
                min="1.5"
                max="8.0"
                step="0.5"
                value={detectionSettings.threshold_sigma ?? 3.5}
                onChange={(e) =>
                  onChangeDetectionSettings?.({ threshold_sigma: parseFloat(e.target.value) })
                }
                className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
              />
              <div className="flex justify-between text-[8px] text-slate-500 mt-0.5">
                <span>1.5σ (Faintest)</span>
                <span>3.5σ (Std)</span>
                <span>8.0σ (Brightest)</span>
              </div>
            </div>

            {/* Assumed PSF FWHM */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-300 mb-1">
                <span className="font-medium">Assumed PSF FWHM</span>
                <span className="font-mono text-slate-200">
                  {(detectionSettings.fwhm_pixels ?? 3.0).toFixed(1)} px
                </span>
              </div>
              <input
                type="range"
                min="1.5"
                max="6.0"
                step="0.5"
                value={detectionSettings.fwhm_pixels ?? 3.0}
                onChange={(e) =>
                  onChangeDetectionSettings?.({ fwhm_pixels: parseFloat(e.target.value) })
                }
                className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
              />
            </div>

            {/* Reset to defaults */}
            <button
              onClick={() =>
                onChangeDetectionSettings?.({
                  max_sources: 500,
                  threshold_sigma: 3.5,
                  fwhm_pixels: 3.0
                })
              }
              className="w-full py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors flex items-center justify-center space-x-1 text-[10px] font-sans"
            >
              <RotateCcw className="w-3 h-3 text-slate-400" />
              <span>Reset Detection Defaults (500 sources)</span>
            </button>
          </div>
        )}

        {/* Tab 2: Display Scaling Settings */}
        {activeTab === "display" && (
          <div className="space-y-3">
            {/* Stretch */}
            <div>
              <label className="text-[10px] text-slate-400 block mb-1 font-sans">Astronomical Stretch</label>
              <div className="grid grid-cols-4 gap-1 text-[10px]">
                {["asinh", "linear", "log", "sqrt"].map((st) => (
                  <button
                    key={st}
                    onClick={() => onChangeSettings?.({ stretch: st })}
                    className={`py-1 rounded border uppercase text-center transition-colors ${
                      settings.stretch === st
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
              <label className="text-[10px] text-slate-400 block mb-1 font-sans">Color Palette</label>
              <select
                value={settings.colormap}
                onChange={(e) => onChangeSettings?.({ colormap: e.target.value })}
                className="w-full bg-black/50 border border-white/10 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="inferno">Inferno (Infrared Standard)</option>
                <option value="viridis">Viridis</option>
                <option value="plasma">Plasma</option>
                <option value="gray">Grayscale</option>
                <option value="magma">Magma</option>
              </select>
            </div>

            {/* Brightness */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5 font-sans">
                <span>Brightness</span>
                <span className="font-mono text-white">{settings.brightness?.toFixed(2)}x</span>
              </div>
              <input
                type="range"
                min="0.4"
                max="2.5"
                step="0.1"
                value={settings.brightness ?? 1.0}
                onChange={(e) => onChangeSettings?.({ brightness: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
              />
            </div>

            {/* Contrast */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5 font-sans">
                <span>Contrast</span>
                <span className="font-mono text-white">{settings.contrast?.toFixed(2)}x</span>
              </div>
              <input
                type="range"
                min="0.4"
                max="2.5"
                step="0.1"
                value={settings.contrast ?? 1.0}
                onChange={(e) => onChangeSettings?.({ contrast: parseFloat(e.target.value) })}
                className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
              />
            </div>

            {/* Percentile Cutoffs */}
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-0.5 font-sans">
                <span>Percentile Cutoffs</span>
                <span className="font-mono text-white">
                  {settings.p_min?.toFixed(1)}% — {settings.p_max?.toFixed(1)}%
                </span>
              </div>
              <div className="space-y-1">
                <input
                  type="range"
                  min="0.0"
                  max="10.0"
                  step="0.5"
                  value={settings.p_min ?? 0.5}
                  onChange={(e) => onChangeSettings?.({ p_min: parseFloat(e.target.value) })}
                  className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
                />
                <input
                  type="range"
                  min="90.0"
                  max="100.0"
                  step="0.5"
                  value={settings.p_max ?? 99.5}
                  onChange={(e) => onChangeSettings?.({ p_max: parseFloat(e.target.value) })}
                  className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
                />
              </div>
            </div>

            {/* Reset button */}
            <button
              onClick={() =>
                onChangeSettings?.({
                  stretch: "asinh",
                  colormap: "inferno",
                  brightness: 1.0,
                  contrast: 1.0,
                  p_min: 0.5,
                  p_max: 99.5
                })
              }
              className="w-full py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors flex items-center justify-center space-x-1 text-[10px] font-sans"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset Display Defaults</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
