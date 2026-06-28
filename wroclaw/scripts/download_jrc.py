# scripts/download_jrc.py
# Downloads JRC Global Surface Water occurrence raster for the Wroclaw AOI.
# Requires earthengine-api or direct tile download.
# Run once before the pipeline.

import os
import requests

# JRC Global Surface Water is available as tiles via direct URL
# Tile covering Poland (Wroclaw ~17E, 51N): 10E_60N
# JRC naming uses lower-left corner — tile covers 10°E-20°E, 50°N-60°N
# URL format from EC JRC data portal

JRC_URL = (
    "https://storage.googleapis.com/global-surface-water/downloads2021/"
    "occurrence/occurrence_10E_60Nv1_4_2021.tif"
)

OUTPUT_PATH = "data/external/jrc_water_wroclaw.tif"


def download_jrc():
    if os.path.exists(OUTPUT_PATH):
        print(f"Already exists: {OUTPUT_PATH}")
        return

    print(f"Downloading JRC Global Surface Water occurrence tile...")
    print(f"Source: {JRC_URL}")

    response = requests.get(JRC_URL, stream=True)
    response.raise_for_status()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Downloaded: {OUTPUT_PATH}")


if __name__ == "__main__":
    download_jrc()