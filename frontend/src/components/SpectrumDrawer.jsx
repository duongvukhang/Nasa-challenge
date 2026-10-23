import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import { Activity, X, Info, AlertCircle } from "lucide-react";
import { api } from "../services/api";

export const SpectrumDrawer = ({
  isOpen,
  onClose,
  observationId,
  selectedSource
}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !observationId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    const targetCoords = selectedSource
      ? {
          pixel_x: selectedSource.pixel_x,
          pixel_y: selectedSource.pixel_y,
          ra_deg: selectedSource.ra_deg ?? undefined,
          dec_deg: selectedSource.dec_deg ?? undefined
        }
      : {};

    api
      .extractSpectrum(observationId, targetCoords)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load spectrum");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, observationId, selectedSource?.id]);

  if (!isOpen) return null;

  const chartData = data?.points?.map((p) => ({
    wavelength: p.wavelength_um,
    flux: p.flux,
    band: p.band
  })) || [];

  return (
    <div className="absolute bottom-16 inset-x-4 sm:inset-x-12 md:inset-x-24 lg:inset-x-48 z-30 pointer-events-auto select-none font-mono">
      <div className="stellarium-glass-dark rounded-2xl p-4 shadow-2xl border border-white/10 text-xs text-slate-300 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-white text-xs uppercase tracking-wider">
              SPHEREx LVF Infrared Spectral Energy Distribution (SED)
            </span>
            {selectedSource && (
              <span className="text-[10px] text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60">
                {selectedSource.id}
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="h-40 flex items-center justify-center space-x-2 text-slate-400">
            <Activity className="w-4 h-4 text-cyan-400 animate-spin" />
            <span>Extracting Linear Variable Filter dispersion channels...</span>
          </div>
        ) : error || chartData.length === 0 ? (
          <div className="h-32 flex flex-col items-center justify-center text-slate-500 text-center">
            <AlertCircle className="w-5 h-5 mb-1.5 opacity-60" />
            <p>No valid spectral measurements extracted at this sky position.</p>
            <p className="text-[10px] text-slate-600">Select an identified source in the active observation field.</p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="h-48 w-full bg-black/40 rounded-xl p-2 border border-white/5">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="wavelength"
                    tick={{ fill: "#94a3b8", fontSize: 10 }}
                    tickFormatter={(v) => `${v.toFixed(2)}µm`}
                  />
                  <YAxis
                    tick={{ fill: "#94a3b8", fontSize: 10 }}
                    tickFormatter={(v) => v.toFixed(1)}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const pt = payload[0].payload;
                        return (
                          <div className="stellarium-glass-dark border border-white/15 p-2 rounded shadow-xl text-[10px] font-mono space-y-0.5">
                            <div className="text-cyan-400 font-bold">λ: {pt.wavelength} µm</div>
                            <div className="text-white">Surface Brightness: {pt.flux} MJy/sr</div>
                            <div className="text-slate-400">Detector Channel: {pt.band}</div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="flux"
                    stroke="#22d3ee"
                    strokeWidth={2}
                    dot={{ r: 4, fill: "#06b6d4" }}
                    activeDot={{ r: 6, fill: "#38bdf8" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-400 px-1 font-sans">
              <span>Wavelength: {chartData[0]?.wavelength.toFixed(2)} µm — {chartData[chartData.length - 1]?.wavelength.toFixed(2)} µm</span>
              <span className="text-cyan-400 font-mono">Unit: MJy/sr (Surface Brightness)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
