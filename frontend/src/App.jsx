import React, { useState, useEffect, useCallback, useRef } from "react";
import { TopToolbar } from "./components/TopToolbar";
import { Sidebar } from "./components/Sidebar";
import { SkyViewer } from "./components/SkyViewer";
import { BottomDock } from "./components/BottomDock";
import { TimeController } from "./components/TimeController";
import { SourceInfoCard } from "./components/SourceInfoCard";
import { DisplaySettingsPopup } from "./components/DisplaySettingsPopup";
import { SpectrumDrawer } from "./components/SpectrumDrawer";
import { PredictionModal } from "./components/PredictionModal";
import { ArchiveModal } from "./components/ArchiveModal";
import { HowItWorksDialog } from "./components/HowItWorksDialog";
import { api } from "./services/api";

export const App = () => {
  // Observations and active state
  const [observations, setObservations] = useState([]);
  const [activeObservationId, setActiveObservationId] = useState(null);
  const [sources, setSources] = useState([]);
  const [selectedSource, setSelectedSource] = useState(null);

  // Observational Overlays state (Stellarium-inspired toggles)
  const [overlaySettings, setOverlaySettings] = useState({
    showSources: true,
    showLabels: true,
    showGrid: false,
    showTrajectories: true,
    showUncertainty: true
  });

  // Display Scaling settings (asinh, colormaps, brightness, contrast)
  const [displaySettings, setDisplaySettings] = useState({
    stretch: "asinh",
    colormap: "inferno",
    brightness: 1.0,
    contrast: 1.0,
    p_min: 0.5,
    p_max: 99.5
  });

  // Tracking and Prediction state
  const [trackData, setTrackData] = useState(null);
  const [predictionData, setPredictionData] = useState(null);

  // UI Panels and Modals
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSpectrumOpen, setIsSpectrumOpen] = useState(false);
  const [isPredictionModalOpen, setIsPredictionModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);
  const [isTimelineVisible, setIsTimelineVisible] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Pre-filled archive coordinates
  const [archiveCoords, setArchiveCoords] = useState({ ra: 276.26, dec: 64.82 });

  // Notifications
  const [notification, setNotification] = useState(null);
  const showToast = (message, type = "info") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  // Toggle overlay setting helper
  const handleToggleOverlay = (key) => {
    setOverlaySettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleUpdateDisplaySettings = (partial) => {
    setDisplaySettings((prev) => ({ ...prev, ...partial }));
  };

  // Fullscreen toggle
  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      setIsFullscreen(false);
    }
  };

  const sourceReqIdRef = useRef(0);

  // Synchronous observation selection with instant state reset
  const handleSelectObservation = useCallback((obsId) => {
    if (obsId === activeObservationId) return;
    setSources([]);
    setSelectedSource(null);
    setTrackData(null);
    setPredictionData(null);
    setActiveObservationId(obsId);
  }, [activeObservationId]);

  // Load and refresh observations
  const refreshObservations = useCallback(async (selectId = null) => {
    try {
      const list = await api.listObservations();
      setObservations(list);
      if (list.length > 0) {
        const targetId = selectId && list.some((o) => o.observation_id === selectId)
          ? selectId
          : list[0].observation_id;
        setActiveObservationId((prev) => {
          if (selectId) return selectId;
          return list.some((o) => o.observation_id === prev) ? prev : targetId;
        });
      } else {
        setActiveObservationId(null);
        setSources([]);
        setSelectedSource(null);
        setTrackData(null);
        setPredictionData(null);
      }
    } catch (err) {
      showToast("Connecting to SkyTrace backend...", "info");
    }
  }, []);

  useEffect(() => {
    refreshObservations();
  }, [refreshObservations]);

  // Sync archive coordinate search center with active observation WCS
  useEffect(() => {
    const active = observations.find((o) => o.observation_id === activeObservationId);
    if (active?.wcs?.has_wcs && active.wcs.crval) {
      setArchiveCoords({
        ra: parseFloat(active.wcs.crval[0].toFixed(4)),
        dec: parseFloat(active.wcs.crval[1].toFixed(4))
      });
    }
  }, [activeObservationId, observations]);

  // Load sources when active observation changes, guarded against race conditions
  useEffect(() => {
    if (!activeObservationId) {
      setSources([]);
      setSelectedSource(null);
      setTrackData(null);
      setPredictionData(null);
      return;
    }

    const currentReqId = ++sourceReqIdRef.current;
    // Clear instantly to guarantee isolation
    setSources([]);
    setSelectedSource(null);
    setTrackData(null);
    setPredictionData(null);

    api
      .getSources(activeObservationId, {
        threshold_sigma: 3.5,
        fwhm_pixels: 3.0,
        max_sources: 120
      })
      .then((res) => {
        if (currentReqId === sourceReqIdRef.current) {
          const detected = res.sources || [];
          setSources(detected);
          if (detected.length > 0) {
            setSelectedSource(detected[0]);
          }
        }
      })
      .catch((err) => {
        if (currentReqId === sourceReqIdRef.current) {
          console.error("Source detection query error:", err);
        }
      });
  }, [activeObservationId]);

  // Track selected source across all loaded observations
  useEffect(() => {
    if (activeObservationId && selectedSource && observations.length > 1) {
      api
        .trackSource(activeObservationId, selectedSource.id, 10.0)
        .then((res) => setTrackData(res))
        .catch(() => setTrackData(null));
    } else {
      setTrackData(null);
    }
  }, [activeObservationId, selectedSource?.id, observations.length]);

  // Action handlers
  const handleUploadFits = async (file) => {
    showToast(`Uploading ${file.name}...`, "info");
    try {
      const meta = await api.uploadFits(file);
      await refreshObservations(meta.observation_id);
      showToast(`Loaded ${file.name}`, "success");
      setIsSidebarOpen(false);
    } catch (err) {
      showToast(err.message || "Upload error", "error");
    }
  };

  const handleLoadDemo = async () => {
    showToast("Loading 3-epoch synthetic SPHEREx demonstration...", "info");
    try {
      const metas = await api.loadDemo();
      await refreshObservations(metas[0]?.observation_id);
      showToast("Loaded 3-epoch simulated field (SIMULATED DEMO)", "warning");
      setIsSidebarOpen(false);
    } catch (err) {
      showToast(err.message || "Demo loading error", "error");
    }
  };

  const handleLoadRealSample = async () => {
    showToast("Loading authentic SPHEREx Level 2 product...", "info");
    try {
      const meta = await api.loadRealSample();
      await refreshObservations(meta.observation_id);
      showToast(`Loaded authentic SPHEREx product: ${meta.filename}`, "success");
      setIsSidebarOpen(false);
    } catch (err) {
      showToast(err.message || "No bundled real file found", "error");
    }
  };

  const handleDeleteObservation = async (obsId) => {
    try {
      await api.deleteObservation(obsId);
      const remaining = observations.filter((o) => o.observation_id !== obsId);
      setObservations(remaining);
      if (activeObservationId === obsId) {
        if (remaining.length > 0) {
          handleSelectObservation(remaining[0].observation_id);
        } else {
          setActiveObservationId(null);
          setSources([]);
          setSelectedSource(null);
          setTrackData(null);
          setPredictionData(null);
        }
      }
      showToast("Removed observation", "info");
    } catch (err) {
      showToast(err.message || "Failed to remove observation", "error");
    }
  };

  const handleClearSession = async () => {
    try {
      await api.clearAllObservations();
      setObservations([]);
      setActiveObservationId(null);
      setSources([]);
      setSelectedSource(null);
      setTrackData(null);
      setPredictionData(null);
      showToast("Active session cleared", "info");
    } catch (err) {
      showToast(err.message || "Failed to clear session", "error");
    }
  };

  const handleSearchCoordinates = (ra, dec) => {
    setArchiveCoords({ ra, dec });
    setIsArchiveModalOpen(true);
  };

  const currentObs = observations.find((o) => o.observation_id === activeObservationId) || null;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-space-950 font-sans select-none">
      {/* 1. Full-Screen Astronomical Canvas (Primary Visual Experience) */}
      <SkyViewer
        observation={currentObs}
        sources={sources}
        selectedSource={selectedSource}
        onSelectSource={setSelectedSource}
        overlaySettings={overlaySettings}
        displaySettings={displaySettings}
        trackData={trackData}
        predictionData={predictionData}
      />

      {/* 2. Top Floating Toolbar */}
      <TopToolbar
        currentObservation={currentObs}
        sources={sources}
        selectedSource={selectedSource}
        onSelectSource={setSelectedSource}
        onSearchCoordinates={handleSearchCoordinates}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        isSettingsOpen={isSettingsOpen}
        onToggleSettings={() => setIsSettingsOpen(!isSettingsOpen)}
        isFullscreen={isFullscreen}
        onToggleFullscreen={handleToggleFullscreen}
      />

      {/* 3. Stellarium-Inspired Collapsible Left Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        observations={observations}
        activeObservationId={activeObservationId}
        onSelectObservation={handleSelectObservation}
        onDeleteObservation={handleDeleteObservation}
        onClearSession={handleClearSession}
        sources={sources}
        selectedSource={selectedSource}
        onSelectSource={setSelectedSource}
        onUploadFits={handleUploadFits}
        onLoadDemo={handleLoadDemo}
        onLoadRealSample={handleLoadRealSample}
        onOpenArchiveModal={() => setIsArchiveModalOpen(true)}
        onOpenHowItWorks={() => setIsHowItWorksOpen(true)}
        displaySettings={displaySettings}
        onChangeDisplaySettings={handleUpdateDisplaySettings}
        overlaySettings={overlaySettings}
        onToggleOverlay={handleToggleOverlay}
        onSearchCoordinates={handleSearchCoordinates}
      />

      {/* 4. Bottom Floating Dock (Stellarium-style Observational Toggles) */}
      <BottomDock
        overlaySettings={overlaySettings}
        onToggleOverlay={handleToggleOverlay}
        isSpectrumOpen={isSpectrumOpen}
        onToggleSpectrum={() => setIsSpectrumOpen(!isSpectrumOpen)}
        isTimelineVisible={isTimelineVisible}
        onToggleTimeline={() => setIsTimelineVisible(!isTimelineVisible)}
        isSettingsOpen={isSettingsOpen}
        onToggleSettings={() => setIsSettingsOpen(!isSettingsOpen)}
      />

      {/* 5. Bottom-Right Observation Time Controller */}
      <TimeController
        observations={observations}
        activeObservationId={activeObservationId}
        onSelectObservation={handleSelectObservation}
        isVisible={isTimelineVisible}
      />

      {/* 6. Selected-Source Floating Info Card */}
      {selectedSource && (
        <SourceInfoCard
          source={selectedSource}
          observation={currentObs}
          onClose={() => setSelectedSource(null)}
          onOpenSpectrum={() => setIsSpectrumOpen(true)}
          onOpenPrediction={() => setIsPredictionModalOpen(true)}
          trackData={trackData}
        />
      )}

      {/* 7. Quick Display Scaling Popup */}
      <DisplaySettingsPopup
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={displaySettings}
        onChangeSettings={handleUpdateDisplaySettings}
      />

      {/* 8. Floating Infrared Spectrum Drawer */}
      <SpectrumDrawer
        isOpen={isSpectrumOpen}
        onClose={() => setIsSpectrumOpen(false)}
        observationId={currentObs?.observation_id}
        selectedSource={selectedSource}
      />

      {/* 9. Prediction & Verification Modal */}
      <PredictionModal
        isOpen={isPredictionModalOpen}
        onClose={() => setIsPredictionModalOpen(false)}
        currentObservation={currentObs}
        selectedSource={selectedSource}
        allObservations={observations}
        onPredictionComputed={(pred) => setPredictionData(pred)}
      />

      {/* 10. NASA/IPAC IRSA Archive Modal */}
      <ArchiveModal
        isOpen={isArchiveModalOpen}
        onClose={() => setIsArchiveModalOpen(false)}
        onObservationLoaded={() => refreshObservations()}
        initialRa={archiveCoords.ra}
        initialDec={archiveCoords.dec}
      />

      {/* 11. Scientific Methodology & Mission Guide */}
      <HowItWorksDialog
        isOpen={isHowItWorksOpen}
        onClose={() => setIsHowItWorksOpen(false)}
      />

      {/* Floating Status Notification Toast */}
      {notification && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-50 pointer-events-none font-mono">
          <div
            className={`px-4 py-1.5 rounded-full text-xs shadow-2xl border flex items-center space-x-2 ${
              notification.type === "success"
                ? "bg-cyan-950/90 text-cyan-200 border-cyan-500/60 shadow-cyan-glow"
                : notification.type === "warning"
                ? "bg-amber-950/90 text-amber-200 border-amber-500/60 shadow-amber-glow"
                : notification.type === "error"
                ? "bg-red-950/90 text-red-200 border-red-500/60"
                : "bg-space-900/90 text-slate-200 border-white/10"
            }`}
          >
            <span>{notification.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};
