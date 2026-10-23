import React, { useState } from "react";
import {
  X,
  Search,
  Database,
  Download,
  AlertCircle,
  ExternalLink,
  Activity
} from "lucide-react";
import { api } from "../services/api";

export const ArchiveModal = ({
  isOpen,
  onClose,
  onObservationLoaded,
  initialRa = 276.26,
  initialDec = 64.82
}) => {
  const [ra, setRa] = useState(initialRa.toString());
  const [dec, setDec] = useState(initialDec.toString());
  const [radius, setRadius] = useState("5.0");
  const [band, setBand] = useState("");
  const [loading, setLoading] = useState(false);
  const [downloadingObsId, setDownloadingObsId] = useState(null);
  const [searchResult, setSearchResult] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSearch = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await api.searchArchive({
        ra_deg: parseFloat(ra) || 0.0,
        dec_deg: parseFloat(dec) || 0.0,
        radius_arcmin: parseFloat(radius) || 5.0,
        band: band || undefined,
        max_records: 20
      });
      setSearchResult(res);
    } catch (err) {
      setError(err.message || "Archive search query failed");
    } finally {
      setLoading(false);
    }
  };

  const handleFetchProduct = async (record) => {
    if (!record.access_url) return;
    setDownloadingObsId(record.obs_id);
    setError(null);

    try {
      await api.fetchArchiveObservation(record.obs_id, record.access_url);
      onObservationLoaded();
      onClose();
    } catch (err) {
      setError(err.message || "Failed to download FITS from IRSA archive");
    } finally {
      setDownloadingObsId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none font-mono">
      <div className="stellarium-glass-dark border border-white/10 w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden text-xs text-slate-300">
        {/* Modal Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-white">
            <Database className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-xs tracking-wider uppercase">
              NASA/IPAC IRSA SPHEREx Archive TAP Search
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 space-y-4 flex-1 overflow-y-auto">
          {/* Query Form */}
          <form onSubmit={handleSearch} className="space-y-3 bg-black/40 p-3 rounded-xl border border-white/5">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">RA (deg, J2000)</label>
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  max="360"
                  value={ra}
                  onChange={(e) => setRa(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Dec (deg, J2000)</label>
                <input
                  type="number"
                  step="0.0001"
                  min="-90"
                  max="90"
                  value={dec}
                  onChange={(e) => setDec(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 font-sans">Search Radius (arcmin)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.1"
                  max="120"
                  value={radius}
                  onChange={(e) => setRadius(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center space-x-2">
                <span className="text-[11px] text-slate-400 font-sans">Detector Channel:</span>
                <select
                  value={band}
                  onChange={(e) => setBand(e.target.value)}
                  className="bg-black/50 border border-white/10 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                >
                  <option value="">All LVF Bands</option>
                  <option value="D1">Band 1 (0.75 - 1.11 µm)</option>
                  <option value="D2">Band 2 (1.11 - 1.64 µm)</option>
                  <option value="D3">Band 3 (1.64 - 2.42 µm)</option>
                  <option value="D4">Band 4 (2.42 - 3.82 µm)</option>
                  <option value="D5">Band 5 (3.82 - 4.42 µm)</option>
                  <option value="D6">Band 6 (4.42 - 5.00 µm)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="px-4 py-1.5 rounded-lg bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 font-bold transition-colors flex items-center space-x-1.5"
              >
                <Search className="w-3.5 h-3.5 text-cyan-400" />
                <span>{loading ? "Querying IRSA..." : "Execute Query"}</span>
              </button>
            </div>
          </form>

          {error && (
            <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800 text-red-300 text-[11px] flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Results List */}
          {searchResult && (
            <div className="space-y-2">
              <div className="flex justify-between text-[11px] text-slate-400 px-1 font-sans">
                <span>Found <strong className="text-white">{searchResult.total_found}</strong> observations in <span className="text-cyan-400 font-mono">spherex.obscore</span></span>
                <span>IVOA TAP Sync</span>
              </div>

              {searchResult.records.length === 0 ? (
                <div className="p-6 rounded-xl bg-black/40 text-center text-slate-500">
                  No SPHEREx observations cover this coordinate radius in the archive.
                  <br />
                  <span className="text-cyan-400 text-[10px]">Try coordinates near RA=276.0°, Dec=65.0° (North Ecliptic Pole deep survey).</span>
                </div>
              ) : (
                <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                  {searchResult.records.map((rec) => {
                    const isDownloading = downloadingObsId === rec.obs_id;
                    return (
                      <div
                        key={rec.obs_id}
                        className="p-2.5 rounded-xl bg-black/40 border border-white/5 hover:border-white/10 flex items-center justify-between transition-colors"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-white">{rec.obs_id}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                              {rec.band || "LVF"}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400">
                            RA {rec.ra_deg.toFixed(4)}°, Dec {rec.dec_deg.toFixed(4)}° • UTC: {rec.date_obs ? rec.date_obs.slice(0, 10) : "N/A"}
                          </div>
                        </div>

                        <button
                          onClick={() => handleFetchProduct(rec)}
                          disabled={isDownloading || !rec.access_url}
                          className="px-3 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 transition-colors flex items-center space-x-1.5 text-xs disabled:opacity-40"
                        >
                          {isDownloading ? (
                            <>
                              <Activity className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                              <span>Loading...</span>
                            </>
                          ) : (
                            <>
                              <Download className="w-3.5 h-3.5 text-cyan-400" />
                              <span>Load into SkyTrace</span>
                            </>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-white/10 bg-black/40 flex items-center justify-between text-[11px] text-slate-500 font-sans">
          <span>Official NASA/IPAC Infrared Science Archive</span>
          <a
            href="https://irsa.ipac.caltech.edu/applications/spherex/"
            target="_blank"
            rel="noreferrer"
            className="text-cyan-400 hover:underline flex items-center space-x-1"
          >
            <span>IRSA Portal</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
};
