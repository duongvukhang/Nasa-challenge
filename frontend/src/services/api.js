const API_BASE = import.meta.env.VITE_BACKEND_URL || "";

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) throw new Error("Backend service unavailable");
    return res.json();
  },

  async listObservations() {
    const res = await fetch(`${API_BASE}/api/observations`);
    if (!res.ok) throw new Error("Failed to fetch observations");
    return res.json();
  },

  async getObservation(id) {
    const res = await fetch(`${API_BASE}/api/observations/${id}`);
    if (!res.ok) throw new Error(`Failed to fetch observation ${id}`);
    return res.json();
  },

  getImageUrl(id, options = {}) {
    const params = new URLSearchParams();
    if (options.stretch) params.append("stretch", options.stretch);
    if (options.colormap) params.append("colormap", options.colormap);
    if (options.p_min !== undefined) params.append("p_min", options.p_min.toString());
    if (options.p_max !== undefined) params.append("p_max", options.p_max.toString());
    if (options.brightness !== undefined) params.append("brightness", options.brightness.toString());
    if (options.contrast !== undefined) params.append("contrast", options.contrast.toString());
    if (options.max_dim !== undefined) params.append("max_dim", options.max_dim.toString());
    return `${API_BASE}/api/observations/${id}/image?${params.toString()}`;
  },

  async getSources(id, params = {}) {
    const query = new URLSearchParams();
    if (params.threshold_sigma !== undefined) query.append("threshold_sigma", params.threshold_sigma.toString());
    if (params.fwhm_pixels !== undefined) query.append("fwhm_pixels", params.fwhm_pixels.toString());
    if (params.max_sources !== undefined) query.append("max_sources", params.max_sources.toString());

    const res = await fetch(`${API_BASE}/api/observations/${id}/sources?${query.toString()}`);
    if (!res.ok) throw new Error("Source detection query failed");
    return res.json();
  },

  async trackSource(referenceObsId, referenceSourceId, matchingRadiusArcsec = 3.0, observationIds = null) {
    const payload = {
      reference_observation_id: referenceObsId,
      reference_source_id: referenceSourceId,
      matching_radius_arcsec: matchingRadiusArcsec
    };
    if (observationIds) {
      payload.observation_ids = observationIds;
    }

    const res = await fetch(`${API_BASE}/api/tracking/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Tracking error" }));
      throw new Error(err.detail || "Tracking calculation failed");
    }
    return res.json();
  },

  async createTrackTask({ referenceObsId, referenceSourceId, matchingRadiusArcsec = 45.0, observationIds = null, trackId = null }) {
    const payload = {
      reference_observation_id: referenceObsId,
      reference_source_id: referenceSourceId,
      matching_radius_arcsec: matchingRadiusArcsec
    };
    if (observationIds) payload.observation_ids = observationIds;
    if (trackId) payload.track_id = trackId;

    const res = await fetch(`${API_BASE}/api/tracking/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Multi-epoch tracking failed" }));
      throw new Error(err.detail || "Multi-epoch tracking task failed");
    }
    return res.json();
  },

  async listTracks() {
    const res = await fetch(`${API_BASE}/api/tracking/tracks`);
    if (!res.ok) throw new Error("Failed to list active tracks");
    return res.json();
  },

  async getTrack(trackId) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}`);
    if (!res.ok) throw new Error(`Failed to fetch track ${trackId}`);
    return res.json();
  },

  async deleteTrack(trackId) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Failed to delete track ${trackId}`);
    return res.json();
  },

  async clearTracks() {
    const res = await fetch(`${API_BASE}/api/tracking/tracks`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to clear tracks");
    return res.json();
  },

  async undoTrack(trackId) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}/undo`, { method: "POST" });
    if (!res.ok) throw new Error(`Failed to undo action on track ${trackId}`);
    return res.json();
  },

  async redoTrack(trackId) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}/redo`, { method: "POST" });
    if (!res.ok) throw new Error(`Failed to redo action on track ${trackId}`);
    return res.json();
  },

  async acceptCandidate(trackId, observationId, candidateSourceId) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ observation_id: observationId, candidate_source_id: candidateSourceId })
    });
    if (!res.ok) throw new Error(`Failed to accept candidate match`);
    return res.json();
  },

  getTrackExportUrl(trackId, format = "json") {
    return `${API_BASE}/api/tracking/tracks/${trackId}/export?format=${format}`;
  },

  async projectCoordinates(obsId, coordinates) {
    const res = await fetch(`${API_BASE}/api/observations/${obsId}/project`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ coordinates })
    });
    if (!res.ok) throw new Error(`Coordinate projection failed`);
    return res.json();
  },

  async pixelToWorld(obsId, pixelX, pixelY) {
    const res = await fetch(`${API_BASE}/api/observations/${obsId}/pixel-to-world?pixel_x=${pixelX}&pixel_y=${pixelY}`);
    if (!res.ok) throw new Error(`Pixel to world transformation failed`);
    return res.json();
  },

  async getDifference(obsId, refObsId) {
    const res = await fetch(`${API_BASE}/api/observations/${obsId}/difference?ref_obs_id=${refObsId}`);
    if (!res.ok) throw new Error(`Difference calculation failed`);
    return res.json();
  },

  getDifferenceImageUrl(obsId, refObsId, options = {}) {
    const params = new URLSearchParams();
    params.append("ref_obs_id", refObsId);
    if (options.colormap) params.append("colormap", options.colormap);
    if (options.p_min !== undefined) params.append("p_min", options.p_min.toString());
    if (options.p_max !== undefined) params.append("p_max", options.p_max.toString());
    if (options.max_dim !== undefined) params.append("max_dim", options.max_dim.toString());
    return `${API_BASE}/api/observations/${obsId}/difference-image?${params.toString()}`;
  },

  async extractSpectrum(obsId, location = {}) {
    const query = new URLSearchParams();
    if (location.pixel_x !== undefined) query.append("pixel_x", location.pixel_x.toString());
    if (location.pixel_y !== undefined) query.append("pixel_y", location.pixel_y.toString());
    if (location.ra_deg !== undefined) query.append("ra_deg", location.ra_deg.toString());
    if (location.dec_deg !== undefined) query.append("dec_deg", location.dec_deg.toString());

    const res = await fetch(`${API_BASE}/api/observations/${obsId}/spectrum?${query.toString()}`);
    if (!res.ok) throw new Error("Spectral extraction failed");
    return res.json();
  },

  async computePrediction(params) {
    const res = await fetch(`${API_BASE}/api/prediction/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params)
    });
    if (!res.ok) throw new Error("Motion prediction calculation failed");
    return res.json();
  },

  async uploadFits(file) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/api/fits/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || "Upload error");
    }
    return res.json();
  },

  async loadDemo() {
    const res = await fetch(`${API_BASE}/api/samples/load-demo`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to load demonstration dataset");
    return res.json();
  },

  async loadRealSample() {
    const res = await fetch(`${API_BASE}/api/samples/load-real`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Sample loading failed" }));
      throw new Error(err.detail || "Failed to load real SPHEREx sample");
    }
    return res.json();
  },

  async searchArchive(params) {
    const query = new URLSearchParams();
    query.append("ra_deg", params.ra_deg.toString());
    query.append("dec_deg", params.dec_deg.toString());
    query.append("radius", (params.radius ?? params.radius_arcmin ?? 5.0).toString());
    query.append("radius_unit", params.radius_unit || "arcmin");
    if (params.start_date) query.append("start_date", params.start_date);
    if (params.end_date) query.append("end_date", params.end_date);
    if (params.band && params.band !== "ALL") query.append("band", params.band);
    if (params.product_type) query.append("product_type", params.product_type);
    if (params.max_records) query.append("max_records", params.max_records.toString());

    const res = await fetch(`${API_BASE}/api/archive/search?${query.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "IRSA search failed" }));
      throw new Error(err.detail || "IRSA SPHEREx archive search failed");
    }
    return res.json();
  },

  async fetchArchiveObservation(obs_id, access_url, band = null) {
    const res = await fetch(`${API_BASE}/api/archive/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ obs_id, access_url, band })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Fetch failed" }));
      throw new Error(err.detail || "Failed to fetch from IRSA archive");
    }
    return res.json();
  },

  async loadArchiveInterval(params) {
    const payload = {
      ra_deg: parseFloat(params.ra_deg) || 0.0,
      dec_deg: parseFloat(params.dec_deg) || 0.0,
      radius: parseFloat(params.radius ?? params.radius_arcmin ?? 5.0),
      radius_unit: params.radius_unit || "arcmin",
      start_date: params.start_date || null,
      end_date: params.end_date || null,
      band: params.band && params.band !== "ALL" ? params.band : null,
      product_type: params.product_type || "Level 2 Science FITS",
      max_records: params.max_records || 50
    };

    const res = await fetch(`${API_BASE}/api/archive/load-interval`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Interval loading failed" }));
      throw new Error(err.detail || "Failed to load observation interval from IRSA archive");
    }
    return res.json();
  },

  async deleteObservation(id) {
    const res = await fetch(`${API_BASE}/api/observations/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`Failed to delete observation ${id}`);
    return res.json();
  },

  async clearAllObservations() {
    const res = await fetch(`${API_BASE}/api/observations`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to clear observations");
    return res.json();
  },

  async getKnownObjects(obsId, radiusArcmin = 30.0) {
    const res = await fetch(`${API_BASE}/api/observations/${obsId}/known-objects?radius_arcmin=${radiusArcmin}`);
    if (!res.ok) throw new Error("Failed to query known solar system objects");
    return res.json();
  },

  async crossMatchTrack(trackId, matchingRadiusArcsec = 15.0) {
    const res = await fetch(`${API_BASE}/api/tracking/tracks/${trackId}/cross-match?matching_radius_arcsec=${matchingRadiusArcsec}`);
    if (!res.ok) throw new Error("Failed to cross-match track with known objects");
    return res.json();
  }
};
