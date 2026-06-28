# scripts/download_jrc.py
# Downloads JRC Global Surface Water occurrence raster for the Jacobabad AOI.
# Run once before the pipeline.
#
# Jacobabad (~68E, 27N) falls in tile 60E_30N
# JRC naming: lower-left corner — tile covers 60°E-70°E, 20°N-30°N

import os
import requests

JRC_URL = (
    "https://storage.googleapis.com/global-surface-water/downloads2021/"
    "occurrence/occurrence_60E_30Nv1_4_2021.tif"
)

OUTPUT_PATH = "data/external/jrc_water_pakistan.tif"


def download_jrc():
    if os.path.exists(OUTPUT_PATH):
        print(f"Already exists: {OUTPUT_PATH}")
        return

    print("Downloading JRC Global Surface Water occurrence tile (60E_20N)...")
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