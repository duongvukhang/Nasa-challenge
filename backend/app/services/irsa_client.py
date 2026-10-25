import os
import math
import uuid
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import httpx
import pyvo
from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.schemas.archive import (
    ArchiveSearchParams,
    ArchiveSearchResponse,
    ArchiveRecord,
    ObservationEpoch,
    EpochProduct
)
from app.config import settings
from app.services.fits_service import fits_service
from app.services.cache_index import cache_index

# Authentic SPHEREx band configurations (Band 1 through 6)
SPHEREX_BANDS = {
    "D1": {"name": "Band 1 (LVF1)", "min_um": 0.75, "max_um": 1.11, "center_um": 0.93},
    "D2": {"name": "Band 2 (LVF2)", "min_um": 1.11, "max_um": 1.64, "center_um": 1.375},
    "D3": {"name": "Band 3 (LVF3)", "min_um": 1.64, "max_um": 2.42, "center_um": 2.03},
    "D4": {"name": "Band 4 (LVF4)", "min_um": 2.42, "max_um": 3.82, "center_um": 3.12},
    "D5": {"name": "Band 5 (LVF5)", "min_um": 3.82, "max_um": 4.42, "center_um": 4.12},
    "D6": {"name": "Band 6 (LVF6)", "min_um": 4.42, "max_um": 5.00, "center_um": 4.71},
}

ALLOWED_HOSTS = {
    "irsa.ipac.caltech.edu",
    "caltech-ipac.github.io",
    "nasa-irsa-spherex.s3.amazonaws.com",
    "localhost",
    "127.0.0.1"
}

ALLOWED_BANDS = {
    "ALL", "D1", "D2", "D3", "D4", "D5", "D6",
    "LVF1", "LVF2", "LVF3", "LVF4", "LVF5", "LVF6",
    "BAND1", "BAND2", "BAND3", "BAND4", "BAND5", "BAND6"
}

class IRSAClient:
    """
    Client for querying the NASA/IPAC Infrared Science Archive (IRSA)
    SPHEREx TAP service (spherex.obscore) and retrieving authenticated products.
    Preserves strict data integrity:
    - Never fabricates observation records or product IDs.
    - Uses exact spherical footprint overlap for offline search.
    - Enforces safe streaming downloads and verified product identity.
    """

    def __init__(self, tap_url: Optional[str] = None, sia_url: Optional[str] = None):
        self.tap_url = tap_url or settings.IRSA_TAP_URL
        self.sia_url = sia_url or settings.IRSA_SIA_URL
        self._tap_service = None

    def _get_tap_service(self):
        if self._tap_service is None:
            self._tap_service = pyvo.dal.TAPService(self.tap_url)
        return self._tap_service

    def convert_radius_to_degrees(self, radius: float, unit: str) -> float:
        """Converts user radius with explicit unit to degrees."""
        u_clean = unit.lower().strip()
        if u_clean in ["arcsec", "arcseconds", "s", '"']:
            return radius / 3600.0
        elif u_clean in ["arcmin", "arcminutes", "m", "'"]:
            return radius / 60.0
        elif u_clean in ["deg", "degree", "degrees", "d", "°"]:
            return radius
        raise ValueError(f"Unsupported radius unit: '{unit}'. Choose 'arcsec', 'arcmin', or 'deg'.")

    def parse_date_to_mjd(self, date_str: str) -> float:
        """Parses ISO or YYYY-MM-DD date string to MJD."""
        try:
            clean_str = date_str.strip()
            if len(clean_str) == 10 and clean_str.count("-") == 2:
                clean_str += "T00:00:00"
            t = Time(clean_str, format="isot", scale="utc")
            return float(t.mjd)
        except Exception:
            raise ValueError(f"Invalid date format: '{date_str}'. Expected 'YYYY-MM-DD' or ISO 8601 string.")

    def validate_search_params(self, params: ArchiveSearchParams) -> Tuple[float, Optional[float], Optional[float]]:
        # 1. Coordinate ranges
        if not (0.0 <= params.ra_deg <= 360.0):
            raise ValueError(f"Right Ascension {params.ra_deg}° must be between 0.0° and 360.0°.")
        if not (-90.0 <= params.dec_deg <= 90.0):
            raise ValueError(f"Declination {params.dec_deg}° must be between -90.0° and +90.0°.")

        # 2. Radius
        radius_deg = self.convert_radius_to_degrees(params.radius, params.radius_unit)
        if radius_deg <= 0.0:
            raise ValueError("Search radius must be strictly greater than 0.")
        if radius_deg > 5.0:
            raise ValueError("Maximum allowed search radius is 5.0 degrees.")

        # 3. Dates
        start_mjd: Optional[float] = None
        end_mjd: Optional[float] = None
        if params.start_date:
            start_mjd = self.parse_date_to_mjd(params.start_date)
        if params.end_date:
            end_mjd = self.parse_date_to_mjd(params.end_date)

        if start_mjd is not None and end_mjd is not None and start_mjd > end_mjd:
            raise ValueError(f"Start date '{params.start_date}' cannot be later than end date '{params.end_date}'.")

        # 4. Band filter validation
        if params.band and params.band.strip().upper() not in ALLOWED_BANDS:
            raise ValueError(
                f"Invalid band filter '{params.band}'. Allowed values: ALL, D1-D6, LVF1-LVF6, BAND1-BAND6."
            )

        return radius_deg, start_mjd, end_mjd

    def build_adql_query(
        self,
        ra_deg: float,
        dec_deg: float,
        radius_deg: float,
        start_mjd: Optional[float],
        end_mjd: Optional[float],
        band: Optional[str],
        max_records: int
    ) -> str:
        """
        Constructs ADQL query with footprint intersection semantics and temporal overlap.
        """
        adql_where = [
            f"INTERSECTS(CIRCLE('ICRS', {ra_deg:.6f}, {dec_deg:.6f}, {radius_deg:.6f}), s_region) = 1"
        ]

        if start_mjd is not None:
            adql_where.append(f"t_max >= {start_mjd:.5f}")
        if end_mjd is not None:
            adql_where.append(f"t_min <= {end_mjd:.5f}")

        if band and band.upper() != "ALL":
            band_clean = band.strip().replace("'", "").upper()
            det_code = band_clean[-1] if band_clean[-1].isdigit() else band_clean
            adql_where.append(f"(energy_bandpassname LIKE '%D{det_code}%' OR energy_bandpassname LIKE '%LVF{det_code}%')")

        where_clause = " AND ".join(adql_where)
        return f"""
            SELECT TOP {max_records}
                obs_id, s_ra, s_dec, energy_bandpassname, em_min, em_max,
                t_min, t_max, t_exptime, access_url, access_format, dataproduct_type,
                target_name, obs_release_date
            FROM spherex.obscore
            WHERE {where_clause}
            ORDER BY t_min ASC
        """

    async def search_archive(self, params: ArchiveSearchParams) -> ArchiveSearchResponse:
        """
        Executes a spatial cone and temporal interval search across SPHEREx observations.
        Queries the live IRSA TAP service. If unreachable, searches verified cached products.
        If cache is empty or doesn't cover region, returns empty results with an explicit error status.
        Never returns fabricated data.
        """
        radius_deg, start_mjd, end_mjd = self.validate_search_params(params)
        adql = self.build_adql_query(
            params.ra_deg, params.dec_deg, radius_deg, start_mjd, end_mjd, params.band, params.max_records
        )

        records: List[ArchiveRecord] = []
        status = "LIVE_ARCHIVE"
        is_offline = False
        notes: List[str] = []
        error_detail: Optional[str] = None

        try:
            tap = self._get_tap_service()
            results = tap.search(adql)

            for row in results:
                t_min = float(row["t_min"]) if row["t_min"] is not None else None
                date_obs_iso = None
                if t_min is not None:
                    try:
                        date_obs_iso = Time(t_min, format="mjd").isot
                    except Exception:
                        pass

                em_min = float(row["em_min"]) if row["em_min"] is not None else None
                em_max = float(row["em_max"]) if row["em_max"] is not None else None
                center_um = ((em_min + em_max) / 2.0) * 1e6 if (em_min and em_max) else None
                band_name = str(row["energy_bandpassname"]) if row.get("energy_bandpassname") else None

                detector_code = None
                if band_name:
                    for d_code in ["D1", "D2", "D3", "D4", "D5", "D6"]:
                        if d_code in band_name.upper():
                            detector_code = d_code
                            break

                obs_id = str(row["obs_id"])
                rec = ArchiveRecord(
                    obs_id=obs_id,
                    filename=f"{obs_id}.fits",
                    ra_deg=round(float(row["s_ra"]), 6),
                    dec_deg=round(float(row["s_dec"]), 6),
                    date_obs=date_obs_iso,
                    mjd_obs=round(t_min, 6) if t_min else None,
                    band=band_name,
                    detector=detector_code,
                    wavelength_center_um=round(center_um, 3) if center_um else None,
                    wavelength_range_um=[round(em_min * 1e6, 2), round(em_max * 1e6, 2)] if (em_min and em_max) else None,
                    access_url=str(row["access_url"]) if row.get("access_url") else None,
                    filesize_bytes=None,
                    data_release=str(row["obs_release_date"]) if row.get("obs_release_date") else None,
                    product_type="Level 2 Science Image",
                    spatial_coverage=f"Circle r={radius_deg:.3f}°",
                    retrieval_status=self._check_cached_status(obs_id),
                    instrument="SPHEREx",
                    service_source="NASA/IPAC IRSA TAP (spherex.obscore)",
                    observation_group_id=self._extract_group_id(obs_id),
                    is_cached_fallback=False,
                    source_origin="live_irsa"
                )
                records.append(rec)

            if len(records) == 0:
                notes.append(
                    "No observations found for these search criteria in the IRSA archive."
                )

        except Exception as net_err:
            # Remote archive query failed or network is sandboxed/offline
            is_offline = True
            # Search authentic verified cache index
            cached_matches = cache_index.search_offline(
                ra_deg=params.ra_deg,
                dec_deg=params.dec_deg,
                radius_deg=radius_deg,
                start_mjd=start_mjd,
                end_mjd=end_mjd,
                band_filter=params.band,
                max_records=params.max_records
            )

            if cached_matches:
                status = "CACHED_FALLBACK"
                for entry in cached_matches:
                    det = entry.get("detector")
                    band_info = SPHEREX_BANDS.get(det, {}) if det else {}
                    b_name = band_info.get("name", f"Band {det}" if det else "LVF")
                    c_um = band_info.get("center_um")
                    w_range = [band_info["min_um"], band_info["max_um"]] if band_info else None
                    crval = entry.get("crval")

                    rec = ArchiveRecord(
                        obs_id=entry["obs_id"],
                        filename=Path(entry["local_path"]).name,
                        ra_deg=round(crval[0], 6) if crval else None,
                        dec_deg=round(crval[1], 6) if crval else None,
                        date_obs=entry.get("date_obs"),
                        mjd_obs=entry.get("mjd_obs"),
                        band=b_name,
                        detector=det,
                        wavelength_center_um=c_um,
                        wavelength_range_um=w_range,
                        access_url=entry.get("source_url"),
                        filesize_bytes=entry.get("filesize_bytes"),
                        data_release=entry.get("version"),
                        product_type="Level 2 Science Image",
                        spatial_coverage="Verified SPHEREx Footprint (Local Cache)",
                        retrieval_status="cached",
                        instrument="SPHEREx",
                        service_source="Verified Local Cache",
                        observation_group_id=self._extract_group_id(entry["obs_id"]),
                        is_cached_fallback=True,
                        source_origin="local_cache",
                        cached_filepath=entry["local_path"]
                    )
                    records.append(rec)

                notes.append(
                    f"IRSA archive unreachable ({type(net_err).__name__}). Displaying {len(records)} matching verified SPHEREx products from local cache."
                )
            else:
                status = "CONNECTION_ERROR"
                records = []
                error_detail = (
                    f"Unable to connect to NASA/IPAC IRSA archive ({type(net_err).__name__}: {str(net_err)}), and no verified cached products match the search region."
                )
                notes.append(
                    "No observations found. The IRSA archive is currently unreachable and no verified cached products cover the requested coordinates."
                )

        epochs = self.group_records_into_epochs(records, is_cached_fallback=is_offline)

        return ArchiveSearchResponse(
            query_params={
                "ra_deg": params.ra_deg,
                "dec_deg": params.dec_deg,
                "radius": params.radius,
                "radius_unit": params.radius_unit,
                "radius_deg": round(radius_deg, 6),
                "start_date": params.start_date,
                "end_date": params.end_date,
                "band": params.band,
                "max_records": params.max_records
            },
            service_status=status,
            is_offline_fallback=is_offline,
            total_found=len(records),
            total_epochs=len(epochs),
            records=records,
            epochs=epochs,
            notes=notes,
            error_detail=error_detail
        )

    def group_records_into_epochs(
        self, records: List[ArchiveRecord], is_cached_fallback: bool = False
    ) -> List[ObservationEpoch]:
        """
        Groups matching products by verified exposure/visit identity.
        Does not merge separate exposures simply because their timestamps are close.
        Preserves individual product WCS, wavelength range, and detector metadata.
        """
        if not records:
            return []

        sorted_records = sorted(
            records,
            key=lambda r: (r.mjd_obs if r.mjd_obs is not None else float("inf"), r.obs_id)
        )

        epochs: List[ObservationEpoch] = []
        current_group_id: Optional[str] = None
        current_group_records: List[ArchiveRecord] = []

        def flush_group(recs: List[ArchiveRecord], epoch_idx: int) -> ObservationEpoch:
            ref = recs[0]
            group_id = ref.observation_group_id or ref.obs_id

            prod_list = []
            for r in recs:
                prod_list.append(
                    EpochProduct(
                        obs_id=r.obs_id,
                        filename=r.filename,
                        band=r.band,
                        detector=r.detector,
                        wavelength_range_um=r.wavelength_range_um,
                        access_url=r.access_url,
                        filesize_bytes=r.filesize_bytes,
                        is_loaded=(r.retrieval_status == "loaded"),
                        is_cached_fallback=r.is_cached_fallback
                    )
                )

            return ObservationEpoch(
                epoch_id=f"epoch_{epoch_idx + 1:02d}_{group_id}",
                epoch_index=epoch_idx,
                date_obs=ref.date_obs,
                mjd_obs=ref.mjd_obs,
                time_delta_days=None,
                pointing_ra_deg=ref.ra_deg,
                pointing_dec_deg=ref.dec_deg,
                products=prod_list,
                selected_product_id=prod_list[0].obs_id if prod_list else None,
                is_loaded=any(p.is_loaded for p in prod_list),
                is_active=False,
                is_cached_fallback=is_cached_fallback
            )

        for rec in sorted_records:
            grp = rec.observation_group_id or self._extract_group_id(rec.obs_id)
            if current_group_id is None:
                current_group_id = grp
                current_group_records = [rec]
            elif grp == current_group_id:
                current_group_records.append(rec)
            else:
                epochs.append(flush_group(current_group_records, len(epochs)))
                current_group_id = grp
                current_group_records = [rec]

        if current_group_records:
            epochs.append(flush_group(current_group_records, len(epochs)))

        # Compute delta days relative to epoch 0
        if epochs and epochs[0].mjd_obs is not None:
            t0 = epochs[0].mjd_obs
            for ep in epochs:
                if ep.mjd_obs is not None:
                    ep.time_delta_days = round(ep.mjd_obs - t0, 3)

        return epochs

    def _extract_group_id(self, obs_id: str) -> str:
        """
        Extracts verified visit/exposure identifier (e.g. '2025W28_1B_0480_4' from '2025W28_1B_0480_4_D1').
        """
        clean = obs_id.replace("level2_", "").replace("spherex_", "")
        parts = clean.split("_")
        if len(parts) >= 4:
            return "_".join(parts[:4])
        elif len(parts) >= 3:
            return "_".join(parts[:3])
        return clean

    def _check_cached_status(self, obs_id: str) -> str:
        active_ids = [o.observation_id for o in fits_service.list_observations()]
        if obs_id in active_ids or f"irsa_{obs_id}" in active_ids:
            return "loaded"

        entry = cache_index.get_entry(obs_id)
        if entry:
            return "cached"

        return "available"

    def validate_url_security(self, url: str) -> str:
        """
        Validates URL scheme, hostname, credentials, and port.
        Raises ValueError if unsafe.
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise ValueError(f"Security error: Invalid scheme '{parsed.scheme}'. Only HTTPS is permitted.")

        if parsed.username or parsed.password:
            raise ValueError("Security error: URLs containing user credentials are not permitted.")

        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError("Security error: Missing hostname in URL.")

        is_allowed = any(host == ah or host.endswith("." + ah) for ah in ALLOWED_HOSTS)
        if not is_allowed:
            raise ValueError(f"Security error: Download target '{host}' is not an authorized NASA/IPAC IRSA domain.")

        if parsed.port and parsed.port not in (443, 8000, 5173):
            raise ValueError(f"Security error: Port {parsed.port} is not authorized.")

        return url

    async def fetch_fits_from_datalink(self, datalink_url: str, obs_id: str) -> Path:
        """
        Validates URL security, streams product with download size cap into temporary .part file,
        validates FITS structure and OBSID identity, atomically moves to cache, and registers in index.
        Never copies another local file or misidentifies products.
        """
        self.validate_url_security(datalink_url)

        safe_obs_id = "".join(c for c in obs_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_obs_id:
            safe_obs_id = str(uuid.uuid4())[:8]

        # 1. Check if already verified in cache
        cached_entry = cache_index.get_entry(safe_obs_id)
        if cached_entry:
            cached_path = Path(cached_entry["local_path"])
            if cached_path.exists() and cached_path.stat().st_size == cached_entry["filesize_bytes"]:
                return cached_path

        # 2. Check local authentic products by real content
        for local_cand in [
            Path("SPHERExLVFSurveyData/level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits"),
            settings.SAMPLES_DIR / "spherex_qr2_deep_2025W18_1B_0001_1_D1.fits",
            settings.CACHE_DIR / "spherex_2025W23_2B_0061_1.fits"
        ]:
            if local_cand.exists() and safe_obs_id in local_cand.name:
                try:
                    reg = cache_index.register_product(local_cand, expected_obs_id=safe_obs_id)
                    return Path(reg["local_path"])
                except Exception:
                    pass

        # 3. Stream download from remote URL with size limit and redirect validation
        dest_cache_path = settings.CACHE_DIR / f"spherex_{safe_obs_id}.fits"
        part_path = settings.CACHE_DIR / f"spherex_{safe_obs_id}_{uuid.uuid4().hex[:8]}.part"

        current_url = datalink_url
        max_redirects = 5

        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=False) as client:
                redirect_count = 0
                while redirect_count < max_redirects:
                    self.validate_url_security(current_url)
                    resp = await client.get(current_url)

                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            raise ValueError(f"HTTP {resp.status_code} redirect without location header")
                        current_url = location
                        redirect_count += 1
                        continue
                    elif resp.status_code == 200:
                        break
                    else:
                        raise ValueError(f"Remote archive returned HTTP {resp.status_code} for '{current_url}'")

                if redirect_count >= max_redirects:
                    raise ValueError(f"Exceeded maximum redirect count ({max_redirects})")

                # Stream response into .part file enforcing size cap
                bytes_downloaded = 0
                with open(part_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        bytes_downloaded += len(chunk)
                        if bytes_downloaded > settings.MAX_UPLOAD_SIZE_BYTES:
                            raise ValueError(
                                f"Download exceeded size cap of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
                            )
                        f.write(chunk)

            # Check if downloaded content is DataLink XML VOTable
            with open(part_path, "rb") as f:
                lead = f.read(100)

            if lead.startswith(b"<?xml") or b"<VOTABLE" in lead:
                # Parse DataLink VOTable to find direct FITS URL (#this)
                try:
                    tree = ET.parse(str(part_path))
                    root = tree.getroot()
                    ns = {"vo": "http://www.ivoa.net/xml/VOTable/v1.3"}
                    fits_url = None
                    for tr in root.findall(".//vo:TR", ns) or root.findall(".//TR"):
                        tds = tr.findall("vo:TD", ns) or tr.findall("TD")
                        td_texts = [td.text for td in tds if td.text]
                        for txt in td_texts:
                            if txt and txt.startswith("https://") and ".fits" in txt:
                                fits_url = txt
                                break
                        if fits_url:
                            break

                    # Clean up temporary XML
                    part_path.unlink(missing_ok=True)
                    if fits_url:
                        # Recursively fetch direct FITS
                        return await self.fetch_fits_from_datalink(fits_url, obs_id)
                except Exception as xml_err:
                    raise ValueError(f"Failed to resolve DataLink document: {xml_err}")

            # 4. Validate FITS structure, science HDU, and identity
            meta = cache_index.validate_file_and_get_metadata(part_path, expected_obs_id=safe_obs_id)

            # Atomically move .part to final destination
            os.replace(str(part_path), str(dest_cache_path))

            # Register in cache index
            entry = cache_index.register_product(
                dest_cache_path,
                expected_obs_id=safe_obs_id,
                source_url=datalink_url,
                download_time=Time.now().isot
            )
            return dest_cache_path

        except Exception as e:
            part_path.unlink(missing_ok=True)
            raise ValueError(f"Unable to retrieve verified FITS product for observation '{obs_id}': {str(e)}")

irsa_client = IRSAClient()
