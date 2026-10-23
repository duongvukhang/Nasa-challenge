import io
import numpy as np
from typing import Optional, Tuple
from PIL import Image
import matplotlib.cm as cm

class ImageRenderer:
    """
    Renders 2D scientific FITS arrays into optimized web images (PNG/WebP).
    Preserves original scientific calibration in backend; applies visualization
    scaling only for display.
    """

    SUPPORTED_COLORMAPS = {
        "inferno": cm.inferno,
        "viridis": cm.viridis,
        "plasma": cm.plasma,
        "magma": cm.magma,
        "cividis": cm.cividis,
        "gray": cm.gray,
        "gist_heat": cm.gist_heat
    }

    @staticmethod
    def render_to_png_bytes(
        data: np.ndarray,
        stretch: str = "asinh",  # 'linear', 'asinh', 'log', 'sqrt'
        colormap: str = "inferno",
        p_min: float = 0.5,
        p_max: float = 99.5,
        custom_vmin: Optional[float] = None,
        custom_vmax: Optional[float] = None,
        brightness: float = 1.0,
        contrast: float = 1.0,
        max_dim: Optional[int] = 1200
    ) -> bytes:
        """
        Transforms raw scientific array to scaled 8-bit RGB PNG image bytes.
        """
        arr = np.array(data, dtype=np.float64, copy=True)
        finite_mask = np.isfinite(arr)

        if not np.any(finite_mask):
            # Empty image fallback
            img = Image.new("RGB", (max(1, arr.shape[1]), max(1, arr.shape[0])), color=(10, 14, 23))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        finite_vals = arr[finite_mask]

        # Determine cutoff values
        if custom_vmin is not None:
            vmin = float(custom_vmin)
        else:
            vmin = float(np.percentile(finite_vals, max(0.0, min(100.0, p_min))))

        if custom_vmax is not None:
            vmax = float(custom_vmax)
        else:
            vmax = float(np.percentile(finite_vals, max(0.0, min(100.0, p_max))))

        if vmax <= vmin:
            vmax = vmin + 1e-6

        # Clip values to [vmin, vmax]
        arr[~finite_mask] = vmin
        np.clip(arr, vmin, vmax, out=arr)

        # Normalize to [0.0, 1.0]
        norm = (arr - vmin) / (vmax - vmin)

        # Apply astronomical stretch function
        stretch_type = (stretch or "asinh").lower()
        if stretch_type == "asinh":
            Q = 8.0
            norm = np.arcsinh(Q * norm) / np.arcsinh(Q)
        elif stretch_type == "log":
            norm = np.log1p(100.0 * norm) / np.log1p(100.0)
        elif stretch_type == "sqrt":
            norm = np.sqrt(norm)

        # Apply contrast & brightness adjustment
        if contrast != 1.0 or brightness != 1.0:
            norm = (norm - 0.5) * contrast + 0.5
            norm = norm * brightness
            np.clip(norm, 0.0, 1.0, out=norm)

        # Invert vertical axis so astronomical Y matches image display
        norm_flipped = np.flipud(norm)

        # Apply colormap
        cmap = ImageRenderer.SUPPORTED_COLORMAPS.get(colormap.lower(), cm.inferno)
        rgba = cmap(norm_flipped)
        rgb_bytes = (rgba[:, :, :3] * 255.0).astype(np.uint8)

        # Convert to PIL Image
        pil_img = Image.fromarray(rgb_bytes, mode="RGB")

        # Downsample for web transfer if image exceeds max_dim
        if max_dim is not None and (pil_img.width > max_dim or pil_img.height > max_dim):
            pil_img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

image_renderer = ImageRenderer()
