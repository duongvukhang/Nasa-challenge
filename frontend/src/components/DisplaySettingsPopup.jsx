import React from "react";
import { Sliders, X, RotateCcw } from "lucide-react";

export const DisplaySettingsPopup = ({
  isOpen,
  onClose,
  settings,
  onChangeSettings
}) => {
  if (!isOpen) return null;

  return (
    <div className="absolute top-14 right-3 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark rounded-2xl p-3.5 shadow-2xl border border-white/10 text-xs text-slate-300 w-68 space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
          <span className="font-bold text-white text-[11px] uppercase tracking-wider flex items-center space-x-1.5">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span>Image Display Scaling</span>
          </span>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Stretch */}
        <div>
          <label className="text-[10px] text-slate-400 block mb-1 font-sans">Astronomical Stretch</label>
          <div className="grid grid-cols-4 gap-1 text-[10px]">
            {["asinh", "linear", "log", "sqrt"].map((st) => (
              <button
                key={st}
                onClick={() => onChangeSettings({ stretch: st })}
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
            onChange={(e) => onChangeSettings({ colormap: e.target.value })}
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
            onChange={(e) => onChangeSettings({ brightness: parseFloat(e.target.value) })}
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
            onChange={(e) => onChangeSettings({ contrast: parseFloat(e.target.value) })}
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
              onChange={(e) => onChangeSettings({ p_min: parseFloat(e.target.value) })}
              className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
            />
            <input
              type="range"
              min="90.0"
              max="100.0"
              step="0.5"
              value={settings.p_max ?? 99.5}
              onChange={(e) => onChangeSettings({ p_max: parseFloat(e.target.value) })}
              className="w-full accent-cyan-400 bg-white/10 h-1.5 rounded cursor-pointer"
            />
          </div>
        </div>

        {/* Reset button */}
        <button
          onClick={() =>
            onChangeSettings({
              stretch: "asinh",
              colormap: "inferno",
              brightness: 1.0,
              contrast: 1.0,
              p_min: 0.5,
              p_max: 99.5
            })
          }
          className="w-full py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-colors flex items-center justify-center space-x-1 text-[10px]"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset to Defaults</span>
        </button>
      </div>
    </div>
  );
};
