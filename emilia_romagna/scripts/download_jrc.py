# scripts/download_jrc.py
# Downloads JRC Global Surface Water occurrence raster for the Emilia-Romagna AOI.
# Run once before the pipeline.
#
# Emilia-Romagna (~44-45N, 11-13E) falls in tile 10E_40N
# (lower-left corner 10E 40N, covers 10-20E, 40-50N)
# JRC naming: tile name = lower-left corner of the 10x10 degree tile

import os
import requests

JRC_URL = (
    "https://storage.googleapis.com/global-surface-water/downloads2021/"
    "occurrence/occurrence_10E_40Nv1_4_2021.tif"
)

OUTPUT_PATH = "data/external/jrc_water_italy.tif"


def download_jrc():
    if os.path.exists(OUTPUT_PATH):
        print(f"Already exists: {OUTPUT_PATH}")
        return

    print("Downloading JRC Global Surface Water occurrence tile (10E_40N, covers 40-50N)...")
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
