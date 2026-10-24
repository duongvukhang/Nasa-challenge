import React, { useState } from "react";
import {
  X,
  Search,
  Database,
  Download,
  AlertCircle,
  ExternalLink,
  Activity,
  Layers,
  Calendar,
  Clock,
  RotateCcw,
  CheckCircle2,
  Sparkles
} from "lucide-react";
import { api } from "../services/api";

export const ArchiveModal = ({
  isOpen,
  onClose,
  onObservationLoaded,
  onObservationsBatchLoaded,
  initialRa = 276.26,
  initialDec = 64.82
}) => {
  const [ra, setRa] = useState(initialRa.toString());
  const [dec, setDec] = useState(initialDec.toString());
  const [radius, setRadius] = useState("5.0");
  const [radiusUnit, setRadiusUnit] = useState("arcmin");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [band, setBand] = useState("");
  const [activeViewTab, setActiveViewTab] = useState("epochs"); // 'epochs' | 'products'

  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [downloadingObsId, setDownloadingObsId] = useState(null);
  const [searchResult, setSearchResult] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleClear = () => {
    setRa(initialRa.toString());
    setDec(initialDec.toString());
    setRadius("5.0");
    setRadiusUnit("arcmin");
    setStartDate("");
    setEndDate("");
    setBand("");
    setSearchResult(null);
    setError(null);
  };

  const validateInputs = () => {
    const raVal = parseFloat(ra);
    const decVal = parseFloat(dec);
    const radVal = parseFloat(radius);

    if (isNaN(raVal) || raVal < 0.0 || raVal > 360.0) {
      throw new Error("Right Ascension must be a valid number between 0.0° and 360.0°.");
    }
    if (isNaN(decVal) || decVal < -90.0 || decVal > 90.0) {
      throw new Error("Declination must be a valid number between -90.0° and +90.0°.");
    }
    if (isNaN(radVal) || radVal <= 0.0) {
      throw new Error("Search radius must be strictly greater than 0.");
    }
    if (startDate && endDate && startDate > endDate) {
      throw new Error("Start date cannot be after end date.");
    }
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setError(null);

    try {
      validateInputs();
    } catch (valErr) {
      setError(valErr.message);
      return;
    }

    setLoading(true);
    try {
      const res = await api.searchArchive({
        ra_deg: parseFloat(ra),
        dec_deg: parseFloat(dec),
        radius: parseFloat(radius),
        radius_unit: radiusUnit,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        band: band || undefined,
        max_records: 50
      });
      setSearchResult(res);
      if (res.epochs && res.epochs.length > 0) {
        setActiveViewTab("epochs");
      } else {
        setActiveViewTab("products");
      }
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
      const meta = await api.fetchArchiveObservation(record.obs_id, record.access_url, record.band);
      if (onObservationLoaded) {
        onObservationLoaded(meta.observation_id);
      }
      onClose();
    } catch (err) {
      setError(err.message || "Failed to download FITS from IRSA archive");
    } finally {
      setDownloadingObsId(null);
    }
  };

  const handleLoadIntervalBatch = async () => {
    setError(null);
    try {
      validateInputs();
    } catch (valErr) {
      setError(valErr.message);
      return;
    }

    setBatchLoading(true);
    try {
      const metas = await api.loadArchiveInterval({
        ra_deg: parseFloat(ra),
        dec_deg: parseFloat(dec),
        radius: parseFloat(radius),
        radius_unit: radiusUnit,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        band: band || undefined
      });

      if (metas && metas.length > 0) {
        if (onObservationsBatchLoaded) {
          onObservationsBatchLoaded(metas);
        } else if (onObservationLoaded) {
          onObservationLoaded(metas[0].observation_id);
        }
        onClose();
      } else {
        setError("No observations found across the specified coordinate and date interval.");
      }
    } catch (err) {
      setError(err.message || "Failed to batch-load interval observations.");
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 select-none font-mono">
      <div className="stellarium-glass-dark border border-white/10 w-full max-w-3xl rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden text-xs text-slate-300">
        {/* Modal Header */}
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-white">
            <Database className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-xs tracking-wider uppercase">
              NASA/IPAC IRSA SPHEREx Simple Image Access (SIA2) & TAP Search
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 space-y-4 flex-1 overflow-y-auto">
          {/* Query Form */}
          <form onSubmit={handleSearch} className="space-y-3 bg-black/40 p-3.5 rounded-xl border border-white/5 font-sans">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5">
              {/* RA */}
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">RA (deg, J2000)</label>
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  max="360"
                  value={ra}
                  onChange={(e) => setRa(e.target.value)}
                  placeholder="276.26"
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Dec */}
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Dec (deg, J2000)</label>
                <input
                  type="number"
                  step="0.0001"
                  min="-90"
                  max="90"
                  value={dec}
                  onChange={(e) => setDec(e.target.value)}
                  placeholder="64.82"
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Radius with selectable unit */}
              <div className="sm:col-span-2">
                <label className="text-[10px] text-slate-400 block mb-1">Search Cone Radius</label>
                <div className="flex space-x-1.5">
                  <input
                    type="number"
                    step="0.1"
                    min="0.01"
                    max="7200"
                    value={radius}
                    onChange={(e) => setRadius(e.target.value)}
                    className="flex-1 bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  <select
                    value={radiusUnit}
                    onChange={(e) => setRadiusUnit(e.target.value)}
                    className="bg-black/60 border border-white/10 rounded px-2 py-1.5 text-cyan-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  >
                    <option value="arcsec">arcsec (")</option>
                    <option value="arcmin">arcmin (')</option>
                    <option value="deg">degrees (°)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Date Interval & Detector Band */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 flex items-center space-x-1">
                  <Calendar className="w-3 h-3 text-cyan-400" />
                  <span>Start Date (UTC)</span>
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1 flex items-center space-x-1">
                  <Calendar className="w-3 h-3 text-cyan-400" />
                  <span>End Date (UTC)</span>
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-white text-xs font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Detector / Band</label>
                <select
                  value={band}
                  onChange={(e) => setBand(e.target.value)}
                  className="w-full bg-black/50 border border-white/10 rounded px-2.5 py-1.5 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                >
                  <option value="">All LVF Bands (D1 - D6)</option>
                  <option value="D1">Band 1: D1 (0.75 - 1.11 µm)</option>
                  <option value="D2">Band 2: D2 (1.11 - 1.64 µm)</option>
                  <option value="D3">Band 3: D3 (1.64 - 2.42 µm)</option>
                  <option value="D4">Band 4: D4 (2.42 - 3.82 µm)</option>
                  <option value="D5">Band 5: D5 (3.82 - 4.42 µm)</option>
                  <option value="D6">Band 6: D6 (4.42 - 5.00 µm)</option>
                </select>
              </div>
            </div>

            {/* Quick interval presets */}
            <div className="flex items-center space-x-1.5 pt-1 text-[10px] font-mono">
              <span className="text-slate-500 font-sans">Interval Presets:</span>
              <button
                type="button"
                onClick={() => { setStartDate("2025-04-01"); setEndDate("2025-07-01"); }}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300"
              >
                Q2 2025 (Deep Survey)
              </button>
              <button
                type="button"
                onClick={() => { setStartDate("2025-01-01"); setEndDate("2025-12-31"); }}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-300"
              >
                All 2025 Epochs
              </button>
              <button
                type="button"
                onClick={() => { setStartDate(""); setEndDate(""); }}
                className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-slate-400"
              >
                Full Archive
              </button>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-2 border-t border-white/10">
              <button
                type="button"
                onClick={handleClear}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors flex items-center space-x-1 text-xs"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Clear Form</span>
              </button>

              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handleLoadIntervalBatch}
                  disabled={batchLoading || loading}
                  className="px-3 py-1.5 rounded-lg bg-emerald-950/70 hover:bg-emerald-900 border border-emerald-600/60 text-emerald-200 font-bold transition-colors flex items-center space-x-1.5 text-xs disabled:opacity-40"
                  title="Loads all distinct epochs in this interval directly into the timeline"
                >
                  {batchLoading ? (
                    <>
                      <Activity className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                      <span>Loading Epochs...</span>
                    </>
                  ) : (
                    <>
                      <Layers className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Load Observations Across Interval</span>
                    </>
                  )}
                </button>

                <button
                  type="submit"
                  disabled={loading || batchLoading}
                  className="px-4 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/70 text-cyan-200 font-bold transition-colors flex items-center space-x-1.5 text-xs disabled:opacity-40 shadow-cyan-glow"
                >
                  {loading ? (
                    <>
                      <Activity className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                      <span>Querying IRSA...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Search Archive</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          {error && (
            <div className="p-3 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-[11px] flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Results Area */}
          {searchResult && (
            <div className="space-y-3">
              {/* Header with Epoch vs Product view tabs */}
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setActiveViewTab("epochs")}
                    className={`px-3 py-1 rounded-lg text-xs font-sans font-bold flex items-center space-x-1.5 transition-colors ${
                      activeViewTab === "epochs"
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>Distinct Epochs ({searchResult.total_epochs})</span>
                  </button>

                  <button
                    onClick={() => setActiveViewTab("products")}
                    className={`px-3 py-1 rounded-lg text-xs font-sans font-bold flex items-center space-x-1.5 transition-colors ${
                      activeViewTab === "products"
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <Database className="w-3.5 h-3.5" />
                    <span>All Products ({searchResult.total_found})</span>
                  </button>
                </div>

                <div className="text-[10px] text-slate-400 font-mono">
                  {searchResult.service_status === "LIVE_ARCHIVE" ? (
                    <span className="text-emerald-400 font-bold flex items-center space-x-1">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Live IRSA Archive</span>
                    </span>
                  ) : searchResult.service_status === "CACHED_FALLBACK" ? (
                    <span className="text-amber-400 font-bold flex items-center space-x-1">
                      <Sparkles className="w-3 h-3" />
                      <span>Cached Offline Fallback</span>
                    </span>
                  ) : (
                    <span className="text-red-400 font-bold flex items-center space-x-1">
                      <AlertCircle className="w-3 h-3" />
                      <span>Connection Error</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Informative Banner for Offline Cached Fallback */}
              {searchResult.is_offline_fallback && searchResult.service_status === "CACHED_FALLBACK" && (
                <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-600/60 text-amber-200 text-xs flex items-start space-x-2.5 font-sans">
                  <AlertCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <div className="font-bold text-[11px] uppercase tracking-wider text-amber-300 flex items-center space-x-1">
                      <span>Offline / Cached-Data Fallback Active</span>
                    </div>
                    <div className="text-[11px] text-amber-200/90 leading-relaxed">
                      The live NASA/IPAC IRSA archive server is currently unreachable. Displaying matching authentic SPHEREx products previously cached in local repository storage. <strong>Offline mode reflects only previously retrieved products and does not imply that the full IRSA archive is available locally.</strong>
                    </div>
                  </div>
                </div>
              )}

              {/* Connection Error Banner when offline and no cached matches exist */}
              {searchResult.service_status === "CONNECTION_ERROR" && (
                <div className="p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-200 text-xs space-y-2 font-sans">
                  <div className="font-bold flex items-center space-x-2 text-red-300">
                    <AlertCircle className="w-4 h-4" />
                    <span>IRSA Archive Connectivity Error</span>
                  </div>
                  <p className="text-[11px] text-red-300/90 leading-relaxed">
                    {searchResult.error_detail || "Unable to reach the NASA/IPAC IRSA archive, and no suitable cached products exist in local repository storage for these coordinates."}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono">
                    Check network access or search coordinates near the North Ecliptic Pole deep survey (RA 276.26°, Dec 64.82°) where local cached products exist.
                  </p>
                  <button
                    type="button"
                    onClick={handleSearch}
                    className="px-3 py-1 rounded bg-red-900/60 hover:bg-red-800 text-white font-mono text-[10px] transition-colors"
                  >
                    Retry Query
                  </button>
                </div>
              )}

              {searchResult.total_found === 0 && searchResult.service_status !== "CONNECTION_ERROR" ? (
                <div className="p-8 rounded-xl bg-black/40 text-center space-y-3 border border-white/5 font-sans">
                  <p className="text-white font-bold text-sm">No observations found for these search criteria</p>
                  <p className="text-xs text-slate-400 max-w-lg mx-auto leading-relaxed">
                    This does not necessarily mean the coordinates lie outside SPHEREx's overall survey coverage. The selected observation time interval, search radius, or detector filter may not contain published Level-2 products in the current data release. You can adjust the search radius, date interval, or data collection where supported.
                  </p>
                  <div className="pt-1">
                    <span className="text-cyan-400 font-mono text-[11px]">
                      Tip: Try searching near the North Ecliptic Pole deep survey (RA 276.26°, Dec 64.82°) with a 5 or 15 arcminute radius.
                    </span>
                  </div>
                </div>
              ) : (
                /* RESULTS LIST */
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {/* TAB 1: EPOCHS VIEW */}
                  {activeViewTab === "epochs" &&
                    searchResult.epochs.map((epoch) => {
                      const primaryProd = epoch.products[0] || {};
                      const isDownloading = downloadingObsId === primaryProd.obs_id;

                      return (
                        <div
                          key={epoch.epoch_id}
                          className="p-3 rounded-xl bg-black/40 border border-white/5 hover:border-white/10 space-y-2 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <span className="font-bold text-white text-xs">{epoch.epoch_id}</span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 font-mono">
                                {epoch.time_delta_days != null ? `Δt: +${epoch.time_delta_days}d` : "Epoch 1"}
                              </span>
                              {epoch.is_cached_fallback ? (
                                <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-amber-950/80 text-amber-300 border border-amber-800/80">
                                  CACHED FALLBACK
                                </span>
                              ) : (
                                <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                                  LIVE IRSA
                                </span>
                              )}
                            </div>

                            <button
                              onClick={() => handleFetchProduct(primaryProd)}
                              disabled={isDownloading || !primaryProd.access_url}
                              className="px-3 py-1 rounded-lg bg-cyan-950/70 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 transition-colors flex items-center space-x-1 text-xs disabled:opacity-40"
                            >
                              {isDownloading ? (
                                <>
                                  <Activity className="w-3 h-3 animate-spin text-cyan-400" />
                                  <span>Loading...</span>
                                </>
                              ) : (
                                <>
                                  <Download className="w-3 h-3 text-cyan-400" />
                                  <span>Load Epoch FITS</span>
                                </>
                              )}
                            </button>
                          </div>

                          <div className="text-[10px] text-slate-400 grid grid-cols-2 gap-1 font-mono">
                            <div>UTC: {epoch.date_obs}</div>
                            <div>MJD: {epoch.mjd_obs.toFixed(4)}</div>
                            <div>Pointing: RA {epoch.pointing_ra_deg.toFixed(4)}°, Dec {epoch.pointing_dec_deg.toFixed(4)}°</div>
                            <div>Available Channels: {epoch.products.map((p) => p.detector || "D1").join(", ")}</div>
                          </div>
                        </div>
                      );
                    })}

                  {/* TAB 2: PRODUCTS VIEW */}
                  {activeViewTab === "products" &&
                    searchResult.records.map((rec) => {
                      const isDownloading = downloadingObsId === rec.obs_id;
                      return (
                        <div
                          key={rec.obs_id}
                          className="p-3 rounded-xl bg-black/40 border border-white/5 hover:border-white/10 flex items-center justify-between transition-colors"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center space-x-2">
                              <span className="font-bold text-white text-xs">{rec.obs_id}</span>
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                                {rec.band || "LVF"}
                              </span>
                              {rec.is_cached_fallback ? (
                                <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-amber-950/80 text-amber-300 border border-amber-800/80">
                                  CACHED LOCAL PRODUCT
                                </span>
                              ) : (
                                <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-800/80">
                                  LIVE IRSA
                                </span>
                              )}
                              <span className="text-[9px] text-slate-500 font-sans">
                                {rec.filesize_bytes ? `${(rec.filesize_bytes / 1e6).toFixed(1)} MB` : "71.6 MB"}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono">
                              RA {rec.ra_deg.toFixed(4)}°, Dec {rec.dec_deg.toFixed(4)}° • UTC: {rec.date_obs ? rec.date_obs.slice(0, 19) : "N/A"}
                            </div>
                            <div className="text-[9px] text-slate-500 font-sans">
                              Source: {rec.service_source}
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
          <span>Official NASA/IPAC Infrared Science Archive (IRSA) • SPHEREx Simple Image Access</span>
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
