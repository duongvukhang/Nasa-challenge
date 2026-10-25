import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
import { TrajectoryInspector } from "./components/TrajectoryInspector";
import { SkyPlotModal } from "./components/SkyPlotModal";
import { TrackListPanel } from "./components/TrackListPanel";
import { ObjectInspectorModal } from "./components/ObjectInspectorModal";
import { SelectedObjectManager } from "./components/SelectedObjectManager";
import { ComparisonViewer } from "./components/ComparisonViewer";
import { api } from "./services/api";

export const App = () => {
  // Observations and active state
  const [observations, setObservations] = useState([]);
  const [activeObservationId, setActiveObservationId] = useState(null);
  const [comparisonObservationId, setComparisonObservationId] = useState(null);
  const [viewMode, setViewMode] = useState("single"); // "single" | "split" | "blink" | "difference"
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

  // Source detection parameters (max_sources, threshold_sigma, fwhm_pixels)
  const [detectionSettings, setDetectionSettings] = useState({
    max_sources: 500,
    threshold_sigma: 3.5,
    fwhm_pixels: 3.0
  });

  // Tracking and Prediction state
  const [trackData, setTrackData] = useState(null);
  const [predictionData, setPredictionData] = useState(null);
  const [tracks, setTracks] = useState({});
  const [activeTrackId, setActiveTrackId] = useState(null);
  const [hiddenTrackIds, setHiddenTrackIds] = useState(new Set());
  const [isTrackingLoading, setIsTrackingLoading] = useState(false);
  const [inspectingTrack, setInspectingTrack] = useState(null);

  // UI Panels and Modals
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSpectrumOpen, setIsSpectrumOpen] = useState(false);
  const [isPredictionModalOpen, setIsPredictionModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);
  const [isTimelineVisible, setIsTimelineVisible] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isTrackListOpen, setIsTrackListOpen] = useState(false);
  const [isTrackInspectorOpen, setIsTrackInspectorOpen] = useState(false);
  const [isSkyPlotOpen, setIsSkyPlotOpen] = useState(false);
  const [isObjectInspectorOpen, setIsObjectInspectorOpen] = useState(false);
  const [excludedSourceIds, setExcludedSourceIds] = useState(new Set());
  const [centerTarget, setCenterTarget] = useState(null);

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

  const handleUpdateDetectionSettings = (partial) => {
    setDetectionSettings((prev) => ({ ...prev, ...partial }));
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
  const trackedTargetRef = useRef(null);
  const trackingTaskIdRef = useRef(0);

  // Multi-epoch source tracking task
  const handleTrackSource = useCallback(
    async (src) => {
      if (!src || !activeObservationId) return;

      // 1. Preserve source ID, starting epoch ID (E0), coordinates, uncertainty
      const startingEpochId = activeObservationId;
      const currentTaskId = ++trackingTaskIdRef.current;
      setIsTrackingLoading(true);

      showToast(`Tracking source ${src.id} across loaded epochs...`, "info");

      try {
        // 2-5. Execute scientific multi-epoch trajectory tracking
        const track = await api.createTrackTask({
          referenceObsId: startingEpochId,
          referenceSourceId: src.id,
          matchingRadiusArcsec: 45.0
        });

        // Ignore if another task superseded
        if (currentTaskId === trackingTaskIdRef.current) {
          // Preserve user active epoch without resetting to E0
          setTracks((prev) => ({
            ...prev,
            [track.track_id]: track
          }));
          setActiveTrackId(track.track_id);
          setTrackData(track);
          setInspectingTrack(track);

          showToast(
            `[${track.quality_status}] Track ${track.track_id}: ${track.detected_epochs_count}/${track.total_eligible_epochs} epochs detected`,
            track.quality_status === "STRONG MATCH" ? "success" : "warning"
          );
        }
      } catch (err) {
        if (currentTaskId === trackingTaskIdRef.current) {
          showToast(err.message || "Multi-epoch tracking task failed", "error");
        }
      } finally {
        if (currentTaskId === trackingTaskIdRef.current) {
          setIsTrackingLoading(false);
        }
      }
    },
    [activeObservationId]
  );

  // Track management handlers
  const handleSelectTrack = useCallback(
    (trackId) => {
      setActiveTrackId(trackId);
      const tr = tracks[trackId];
      if (tr) {
        setInspectingTrack(tr);
        setTrackData(tr);
      }
    },
    [tracks]
  );

  const handleInspectTrack = useCallback((tr) => {
    setInspectingTrack(tr);
    setIsTrackInspectorOpen(true);
  }, []);

  const handleOpenSkyPlot = useCallback((tr) => {
    setInspectingTrack(tr);
    setIsSkyPlotOpen(true);
  }, []);

  const handleDeleteTrack = useCallback(
    async (trackId) => {
      try {
        await api.deleteTrack(trackId);
      } catch (_) {}
      setTracks((prev) => {
        const next = { ...prev };
        delete next[trackId];
        return next;
      });
      if (activeTrackId === trackId) {
        setActiveTrackId(null);
        setTrackData(null);
        setInspectingTrack(null);
      }
      showToast(`Track ${trackId} deleted`, "info");
    },
    [activeTrackId]
  );

  const handleStopInspectTrack = useCallback(
    async (trackId = null) => {
      const targetId = trackId || activeTrackId || inspectingTrack?.track_id;
      setIsTrackInspectorOpen(false);
      if (targetId) {
        await handleDeleteTrack(targetId);
      } else {
        setTracks({});
        setActiveTrackId(null);
        setTrackData(null);
        setInspectingTrack(null);
      }
      showToast("Trajectory and dots removed", "info");
    },
    [activeTrackId, inspectingTrack, handleDeleteTrack]
  );

  const handleClearTracks = useCallback(async () => {
    try {
      await api.clearTracks();
    } catch (_) {}
    setTracks({});
    setActiveTrackId(null);
    setTrackData(null);
    setInspectingTrack(null);
    showToast("All tracks cleared", "info");
  }, []);

  const handleToggleTrackVisibility = useCallback((trackId) => {
    setHiddenTrackIds((prev) => {
      const next = new Set(prev);
      if (next.has(trackId)) next.delete(trackId);
      else next.add(trackId);
      return next;
    });
  }, []);

  // Selected object management handlers: inspect, delete, center
  const handleDeleteSource = useCallback(
    (sourceId) => {
      if (!sourceId) return;

      // 1. Add to excluded list so re-detections don't bring it back
      setExcludedSourceIds((prev) => new Set([...prev, sourceId]));

      // 2. Remove from active sources array
      setSources((prev) => prev.filter((s) => s.id !== sourceId));

      // 3. If an active track references this source, delete that track
      if (activeTrackId && tracks[activeTrackId]?.reference_source_id === sourceId) {
        handleDeleteTrack(activeTrackId);
      }

      // 4. If currently selected, clear selection
      if (selectedSource?.id === sourceId) {
        setSelectedSource(null);
        trackedTargetRef.current = null;
        setTrackData(null);
      }

      showToast(`Deleted object ${sourceId} from observation catalog`, "info");
    },
    [activeTrackId, tracks, handleDeleteTrack, selectedSource?.id]
  );

  const handleCenterOnSource = useCallback((source) => {
    if (!source || source.pixel_x == null || source.pixel_y == null) return;
    setCenterTarget({
      pixel_x: source.pixel_x,
      pixel_y: source.pixel_y,
      timestamp: Date.now()
    });
    showToast(`Centered on ${source.id}`, "info");
  }, []);

  const handleInspectSource = useCallback((source) => {
    if (source) {
      setSelectedSource(source);
      setIsObjectInspectorOpen(true);
    }
  }, []);

  // Unified source selection handler
  const handleSelectSource = useCallback(
    (src) => {
      if (!src) {
        setSelectedSource(null);
        trackedTargetRef.current = null;
        setTrackData(null);
        setPredictionData(null);
        return;
      }

      setSelectedSource(src);
      trackedTargetRef.current = {
        id: src.id,
        obsId: activeObservationId,
        ra: src.ra_deg,
        dec: src.dec_deg,
        pixelX: src.pixel_x,
        pixelY: src.pixel_y
      };

      // Check if this source belongs to an existing active track in the current observation
      const trackList = Object.values(tracks);
      const associatedTrack = trackList.find((tr) => {
        const ep = tr?.timeline?.find((e) => e.observation_id === activeObservationId);
        return ep?.is_measured && ep?.matched_source_id === src.id && ep?.status === "Likely match";
      });

      if (associatedTrack) {
        setActiveTrackId(associatedTrack.track_id);
        setTrackData(associatedTrack);
      } else {
        // If clicking an unassociated source, clear active track context to avoid stale display
        setActiveTrackId(null);
        setTrackData(null);
      }
    },
    [activeObservationId, tracks]
  );

  // Determine the active track associated with the selected source in the current observation
  const selectedSourceTrack = useMemo(() => {
    if (!activeObservationId) return null;
    if (selectedSource) {
      const trackList = Object.values(tracks);
      for (const tr of trackList) {
        const epMatch = tr?.timeline?.find((ep) => ep.observation_id === activeObservationId);
        if (epMatch?.is_measured && epMatch.matched_source_id === selectedSource.id && epMatch.status === "Likely match") {
          return tr;
        }
      }
      return null;
    }
    return activeTrackId && tracks[activeTrackId] ? tracks[activeTrackId] : trackData;
  }, [selectedSource, activeObservationId, tracks, activeTrackId, trackData]);

  // Switch observation epoch WITHOUT resetting the user's selected object or track data
  const handleSelectObservation = useCallback((obsId) => {
    if (obsId === activeObservationId) return;
    setActiveObservationId(obsId);
  }, [activeObservationId]);

  // Load and refresh observations and persisted tracks
  const refreshObservations = useCallback(async (selectId = null) => {
    try {
      const [list, loadedTracks] = await Promise.all([
        api.listObservations(),
        api.listTracks().catch(() => [])
      ]);
      setObservations(list);
      if (Array.isArray(loadedTracks) && loadedTracks.length > 0) {
        const tracksMap = {};
        loadedTracks.forEach((tr) => {
          if (tr?.track_id) {
            tracksMap[tr.track_id] = tr;
          }
        });
        setTracks(tracksMap);
      }
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
        trackedTargetRef.current = null;
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

  // Keep comparisonObservationId synchronized to a valid alternate observation
  useEffect(() => {
    if (observations.length >= 2) {
      setComparisonObservationId((prev) => {
        if (prev && prev !== activeObservationId && observations.some((o) => o.observation_id === prev)) {
          return prev;
        }
        const alt = observations.find((o) => o.observation_id !== activeObservationId);
        return alt ? alt.observation_id : null;
      });
    } else {
      setComparisonObservationId(null);
      if (viewMode !== "single") setViewMode("single");
    }
  }, [observations, activeObservationId, viewMode]);

  // Load sources when active observation or detection parameters change
  useEffect(() => {
    if (!activeObservationId) {
      setSources([]);
      setSelectedSource(null);
      trackedTargetRef.current = null;
      setTrackData(null);
      setPredictionData(null);
      return;
    }

    const currentReqId = ++sourceReqIdRef.current;
    const timer = setTimeout(() => {
      api
        .getSources(activeObservationId, {
          threshold_sigma: detectionSettings.threshold_sigma ?? 3.5,
          fwhm_pixels: detectionSettings.fwhm_pixels ?? 3.0,
          max_sources: detectionSettings.max_sources ?? 500
        })
        .then((res) => {
          if (currentReqId === sourceReqIdRef.current) {
            const detected = (res.sources || []).filter((s) => !excludedSourceIds.has(s.id));
            setSources(detected);

            // Maintain tracked object association across epochs using tracking service associations
            const currentTrack = (activeTrackId && tracks[activeTrackId]) || trackData;
            if (currentTrack?.timeline) {
              const epMatch = currentTrack.timeline.find((ep) => ep.observation_id === activeObservationId);
              // Only confirmed/accepted detections associated with the track are selected
              if (epMatch?.is_measured && epMatch.status === "Likely match" && epMatch.matched_source_id) {
                const matched = detected.find((s) => s.id === epMatch.matched_source_id);
                setSelectedSource(matched || null);
              } else {
                // When target is not detected, outside FOV, or ambiguous in this observation:
                // Strictly do NOT create a fake detection or display predicted position as an observed source
                setSelectedSource(null);
              }
            } else if (trackedTargetRef.current) {
              if (trackedTargetRef.current.obsId !== activeObservationId) {
                setSelectedSource(null);
                trackedTargetRef.current = null;
              }
            }
          }
        })
        .catch((err) => {
          if (currentReqId === sourceReqIdRef.current) {
            console.error("Source detection query error:", err);
          }
        });
    }, 150);

    return () => clearTimeout(timer);
  }, [activeObservationId, detectionSettings, tracks, activeTrackId, trackData, excludedSourceIds]);

  // Synchronize selected source when active track or trackData finishes resolving
  useEffect(() => {
    const currentTrack = (activeTrackId && tracks[activeTrackId]) || trackData;
    if (!currentTrack || !activeObservationId || sources.length === 0) return;
    const epMatch = currentTrack.timeline?.find((ep) => ep.observation_id === activeObservationId);
    if (epMatch?.is_measured && epMatch.status === "Likely match" && epMatch.matched_source_id) {
      const found = sources.find((s) => s.id === epMatch.matched_source_id);
      if (found && selectedSource?.id !== found.id) {
        // Only auto-synchronize if no source is currently selected or current selected source is already part of this track
        const isCurrentSourcePartOfTrack = selectedSource && currentTrack.timeline?.some(
          (ep) => ep.matched_source_id === selectedSource.id
        );
        if (!selectedSource || isCurrentSourcePartOfTrack) {
          setSelectedSource(found);
        }
      }
    }
  }, [tracks, activeTrackId, trackData, activeObservationId, sources, selectedSource]);

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
      trackingTaskIdRef.current++;
      await api.clearAllObservations();
      setObservations([]);
      setActiveObservationId(null);
      setSources([]);
      setSelectedSource(null);
      setTrackData(null);
      setPredictionData(null);
      setTracks({});
      setActiveTrackId(null);
      setInspectingTrack(null);
      showToast("Active session cleared", "info");
    } catch (err) {
      showToast(err.message || "Failed to clear session", "error");
    }
  };

  const handleSearchCoordinates = (ra, dec) => {
    setArchiveCoords({ ra, dec });
    setIsArchiveModalOpen(true);
  };

  const handleArchiveObservationLoaded = async (obsId) => {
    await refreshObservations(obsId);
    showToast("Loaded authentic SPHEREx observation from IRSA archive", "success");
  };

  const handleObservationsBatchLoaded = (loadedMetas) => {
    if (loadedMetas && loadedMetas.length > 0) {
      setObservations(loadedMetas);
      handleSelectObservation(loadedMetas[0].observation_id);
      showToast(`Loaded ${loadedMetas.length} distinct epochs from IRSA archive into timeline`, "success");
    }
  };

  const currentObs = observations.find((o) => o.observation_id === activeObservationId) || null;
  const comparisonObs = observations.find((o) => o.observation_id === comparisonObservationId) || null;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-space-950 font-sans select-none">
      {/* 1. Full-Screen Astronomical Canvas (Primary Visual Experience) */}
      {viewMode === "single" || !comparisonObs ? (
        <SkyViewer
          observation={currentObs}
          sources={sources}
          selectedSource={selectedSource}
          onSelectSource={handleSelectSource}
          overlaySettings={overlaySettings}
          displaySettings={displaySettings}
          tracks={tracks}
          activeTrackId={activeTrackId}
          onSelectTrack={handleSelectTrack}
          hiddenTrackIds={hiddenTrackIds}
          trackData={trackData}
          predictionData={predictionData}
          centerTarget={centerTarget}
        />
      ) : (
        <ComparisonViewer
          viewMode={viewMode}
          targetObservation={currentObs}
          referenceObservation={comparisonObs}
          sources={sources}
          selectedSource={selectedSource}
          onSelectSource={handleSelectSource}
          tracks={tracks}
          activeTrackId={activeTrackId}
          onSelectTrack={handleSelectTrack}
          hiddenTrackIds={hiddenTrackIds}
          overlaySettings={overlaySettings}
          displaySettings={displaySettings}
          onChangeViewMode={setViewMode}
        />
      )}

      {/* 2. Top Floating Toolbar */}
      <TopToolbar
        currentObservation={currentObs}
        observations={observations}
        sources={sources}
        selectedSource={selectedSource}
        onSelectSource={handleSelectSource}
        onSearchCoordinates={handleSearchCoordinates}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        isSettingsOpen={isSettingsOpen}
        onToggleSettings={() => setIsSettingsOpen(!isSettingsOpen)}
        isFullscreen={isFullscreen}
        onToggleFullscreen={handleToggleFullscreen}
        viewMode={viewMode}
        onChangeViewMode={setViewMode}
        comparisonObsId={comparisonObservationId}
        onChangeComparisonObsId={setComparisonObservationId}
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
        onSelectSource={handleSelectSource}
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
        isTrackListOpen={isTrackListOpen}
        onToggleTrackList={() => setIsTrackListOpen(!isTrackListOpen)}
        tracksCount={Object.keys(tracks).length}
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
          onClose={() => handleSelectSource(null)}
          onOpenSpectrum={() => setIsSpectrumOpen(true)}
          onOpenPrediction={() => setIsPredictionModalOpen(true)}
          trackData={trackData}
          activeTrack={selectedSourceTrack}
          onTrackSource={handleTrackSource}
          onInspectTrack={handleInspectTrack}
          onStopInspectTrack={handleStopInspectTrack}
          onOpenSkyPlot={handleOpenSkyPlot}
          isTrackingLoading={isTrackingLoading}
          onInspectSource={handleInspectSource}
          onDeleteSource={handleDeleteSource}
          onCenterSource={handleCenterOnSource}
        />
      )}

      {/* 6b. Dedicated Floating Tool: Selected Object Manager (Inspect / Delete / Center / Track) */}
      {selectedSource && (
        <SelectedObjectManager
          selectedSource={selectedSource}
          observation={currentObs}
          activeTrack={selectedSourceTrack}
          onInspect={() => setIsObjectInspectorOpen(true)}
          onDelete={handleDeleteSource}
          onCenter={handleCenterOnSource}
          onTrack={handleTrackSource}
          onStopInspectTrack={handleStopInspectTrack}
          onOpenSpectrum={() => setIsSpectrumOpen(true)}
          onDeselect={() => handleSelectSource(null)}
        />
      )}

      {/* 6c. Comprehensive Astronomical Object Inspector Modal */}
      <ObjectInspectorModal
        isOpen={isObjectInspectorOpen}
        onClose={() => setIsObjectInspectorOpen(false)}
        source={selectedSource}
        observation={currentObs}
        activeTrack={selectedSourceTrack}
        onDeleteSource={handleDeleteSource}
        onCenterSource={handleCenterOnSource}
        onOpenSpectrum={() => setIsSpectrumOpen(true)}
        onOpenPrediction={() => setIsPredictionModalOpen(true)}
        onTrackSource={handleTrackSource}
        onStopInspectTrack={handleStopInspectTrack}
      />

      {/* 7. Active Multi-Epoch Track List Panel */}
      <TrackListPanel
        isOpen={isTrackListOpen}
        onClose={() => setIsTrackListOpen(false)}
        tracks={tracks}
        activeTrackId={activeTrackId}
        onSelectTrack={handleSelectTrack}
        onInspectTrack={handleInspectTrack}
        onOpenSkyPlot={handleOpenSkyPlot}
        onDeleteTrack={handleDeleteTrack}
        onClearTracks={handleClearTracks}
        hiddenTrackIds={hiddenTrackIds}
        onToggleTrackVisibility={handleToggleTrackVisibility}
      />

      {/* 8. Trajectory Quality Inspector */}
      <TrajectoryInspector
        isOpen={isTrackInspectorOpen}
        onClose={() => setIsTrackInspectorOpen(false)}
        track={inspectingTrack || (activeTrackId ? tracks[activeTrackId] : null)}
        onOpenSkyPlot={handleOpenSkyPlot}
        onFocusTrack={(tr) => {
          if (tr.reference_observation_id) {
            handleSelectObservation(tr.reference_observation_id);
          }
        }}
        onDeleteTrack={handleDeleteTrack}
        onSelectObservation={handleSelectObservation}
        onStopInspect={handleStopInspectTrack}
        onUpdateTrack={(updated) => {
          setTracks((prev) => ({ ...prev, [updated.track_id]: updated }));
          setInspectingTrack(updated);
          if (activeTrackId === updated.track_id) setTrackData(updated);
        }}
      />

      {/* 9. Historical Sky-Coordinate Plot Modal */}
      <SkyPlotModal
        isOpen={isSkyPlotOpen}
        onClose={() => setIsSkyPlotOpen(false)}
        track={inspectingTrack || (activeTrackId ? tracks[activeTrackId] : null)}
        onSelectObservation={(obsId) => {
          handleSelectObservation(obsId);
          setIsSkyPlotOpen(false);
        }}
      />

      {/* 10. Quick Display Scaling & Source Detection Popup */}
      <DisplaySettingsPopup
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={displaySettings}
        onChangeSettings={handleUpdateDisplaySettings}
        detectionSettings={detectionSettings}
        onChangeDetectionSettings={handleUpdateDetectionSettings}
        sourcesCount={sources.length}
      />

      {/* 11. Floating Infrared Spectrum Drawer */}
      <SpectrumDrawer
        isOpen={isSpectrumOpen}
        onClose={() => setIsSpectrumOpen(false)}
        observationId={currentObs?.observation_id}
        selectedSource={selectedSource}
      />

      {/* 12. Prediction & Verification Modal */}
      <PredictionModal
        isOpen={isPredictionModalOpen}
        onClose={() => setIsPredictionModalOpen(false)}
        currentObservation={currentObs}
        selectedSource={selectedSource}
        activeTrack={activeTrackId ? tracks[activeTrackId] : null}
        allObservations={observations}
        onPredictionComputed={(pred) => setPredictionData(pred)}
      />

      {/* 13. NASA/IPAC IRSA Archive Modal */}
      <ArchiveModal
        isOpen={isArchiveModalOpen}
        onClose={() => setIsArchiveModalOpen(false)}
        onObservationLoaded={handleArchiveObservationLoaded}
        onObservationsBatchLoaded={handleObservationsBatchLoaded}
        initialRa={archiveCoords.ra}
        initialDec={archiveCoords.dec}
      />

      {/* 14. Scientific Methodology & Mission Guide */}
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
