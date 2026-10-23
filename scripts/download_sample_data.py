#!/usr/bin/env python3
"""
SkyTrace — SPHEREx Sample Data Retrieval Script
Downloads authentic public SPHEREx data products from NASA/IPAC IRSA.
"""

import sys
import os
from pathlib import Path
import httpx
import pyvo

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "backend" / "data" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Documented public Level 2 SPHEREx products from IRSA QR2 Deep survey
SAMPLE_PRODUCTS = [
    {
        "name": "spherex_qr2_deep_2025W18_1B_0001_1_D1.fits",
        "obs_id": "2025W18_1B_0001_1",
        "band": "SPHEREx-D1 (0.75 - 1.11 um)",
        "datalink_url": "https://irsa.ipac.caltech.edu/datalink/links/spherex?ID=ivo://irsa.ipac/spherex_qr2_deep?2025W18_1B_0001_1/D1",
        "direct_url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W18_1B/l2b-v20-2025-241/1/level2_2025W18_1B_0001_1D1_spx_l2b-v20-2025-241.fits"
    }
]

def download_samples():
    print("=" * 70)
    print("SkyTrace: Downloading authentic SPHEREx data from NASA/IPAC IRSA...")
    print("=" * 70)

    for item in SAMPLE_PRODUCTS:
        dest = SAMPLES_DIR / item["name"]
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"[Exists] {item['name']} already exists ({dest.stat().st_size / (1024*1024):.2f} MB). Skipping.")
            continue

        print(f"[Downloading] {item['name']} from:\n  {item['direct_url']}")
        try:
            with httpx.stream("GET", item["direct_url"], timeout=120.0, follow_redirects=True) as response:
                if response.status_code != 200:
                    print(f"[Error] Failed with status code {response.status_code}")
                    continue

                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 512):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            sys.stdout.write(f"\r  Progress: {downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB ({pct:.1f}%)")
                            sys.stdout.flush()

            print(f"\n[Complete] Successfully saved to {dest}")
        except Exception as e:
            print(f"\n[Error] Exception during download: {e}")
            if dest.exists():
                dest.unlink()

if __name__ == "__main__":
    download_samples()
