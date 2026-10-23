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
    query.append("radius_arcmin", params.radius_arcmin.toString());
    if (params.band) query.append("band", params.band);
    if (params.max_records) query.append("max_records", params.max_records.toString());

    const res = await fetch(`${API_BASE}/api/archive/search?${query.toString()}`);
    if (!res.ok) throw new Error("IRSA SPHEREx archive search failed");
    return res.json();
  },

  async fetchArchiveObservation(obs_id, access_url) {
    const res = await fetch(`${API_BASE}/api/archive/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ obs_id, access_url })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Fetch failed" }));
      throw new Error(err.detail || "Failed to fetch from IRSA archive");
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
  }
};
