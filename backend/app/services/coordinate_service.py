import math
from typing import Optional, Tuple, Dict, Any
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord, Angle
import astropy.units as u

class CoordinateService:
    """
    Handles celestial coordinate transformations, formatting, and angular separations.
    Strictly reports when WCS is missing and never fabricates coordinates.
    """

    @staticmethod
    def pixel_to_sky(astropy_wcs: Optional[WCS], x: float, y: float) -> Optional[Tuple[float, float]]:
        """
        Converts 0-indexed pixel coordinates to RA, Dec (J2000 degrees).
        Returns None if WCS is missing or non-celestial.
        """
        if astropy_wcs is None or not astropy_wcs.is_celestial:
            return None
        try:
            coord = astropy_wcs.pixel_to_world(x, y)
            return float(coord.ra.deg), float(coord.dec.deg)
        except Exception:
            return None

    @staticmethod
    def sky_to_pixel(astropy_wcs: Optional[WCS], ra_deg: float, dec_deg: float) -> Optional[Tuple[float, float]]:
        """
        Converts celestial RA, Dec (degrees) to 0-indexed pixel coordinates (x, y).
        """
        if astropy_wcs is None or not astropy_wcs.is_celestial:
            return None
        try:
            coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
            x, y = astropy_wcs.world_to_pixel(coord)
            return float(x), float(y)
        except Exception:
            return None

    @staticmethod
    def angular_separation_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
        """
        Computes great-circle angular separation between two sky points in arcseconds.
        """
        c1 = SkyCoord(ra=ra1 * u.deg, dec=dec1 * u.deg, frame="icrs")
        c2 = SkyCoord(ra=ra2 * u.deg, dec=dec2 * u.deg, frame="icrs")
        sep = c1.separation(c2)
        return float(sep.arcsec)

    @staticmethod
    def position_angle_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
        """
        Computes position angle from point 1 to point 2 (East of North, 0..360 deg).
        """
        c1 = SkyCoord(ra=ra1 * u.deg, dec=dec1 * u.deg, frame="icrs")
        c2 = SkyCoord(ra=ra2 * u.deg, dec=dec2 * u.deg, frame="icrs")
        pa = c1.position_angle(c2)
        return float(pa.deg)

    @staticmethod
    def format_sexagesimal(ra_deg: Optional[float], dec_deg: Optional[float]) -> Dict[str, str]:
        """
        Formats RA and Dec as standard astronomical strings.
        """
        if ra_deg is None or dec_deg is None:
            return {
                "ra_str": "N/A",
                "dec_str": "N/A",
                "combined": "No celestial coordinates (WCS unavailable)"
            }
        try:
            coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
            ra_str = coord.ra.to_string(unit=u.hour, sep=":", precision=2, pad=True)
            dec_str = coord.dec.to_string(unit=u.deg, sep=":", precision=1, alwayssign=True, pad=True)
            return {
                "ra_str": f"{ra_str} ({ra_deg:.5f}°)",
                "dec_str": f"{dec_str} ({dec_deg:.5f}°)",
                "combined": f"RA {ra_str}, Dec {dec_str} (J2000)"
            }
        except Exception:
            return {
                "ra_str": f"{ra_deg:.5f}°",
                "dec_str": f"{dec_deg:.5f}°",
                "combined": f"RA {ra_deg:.5f}°, Dec {dec_deg:.5f}°"
            }

coordinate_service = CoordinateService()
