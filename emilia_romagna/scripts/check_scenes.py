# scripts/check_scenes.py
# Checks Sentinel-1 scene availability on CDSE for target dates over Emilia-Romagna AOI.
# Run this BEFORE starting the pipeline to confirm all scenes are available.
# If a date returns MISSING, adjust by +/- 1 day and retry.

import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv("config/.env")

CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

# Emilia-Romagna AOI bounding box
AOI = [11.0, 43.8, 13.0, 45.0]  # lon_min, lat_min, lon_max, lat_max

# Candidate dates — verify these before running the full pipeline.
# S-1A 12-day repeat; only S-1A was operational in May 2023 (S-1B was down).
# Flooding peaked 16-18 May 2023. Adjust dates by +/-1 if MISSING.
TARGET_DATES = {
    "pre":  "2023-05-05",
    "post": "2023-05-17",
}

ORBIT_DIRECTION = "DESCENDING"


def get_token():
    resp = requests.post(
        CDSE_TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": os.getenv("CDSE_USER"),
            "password": os.getenv("CDSE_PASSWORD"),
        }
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_scene(date_str, token):
    lon_min, lat_min, lon_max, lat_max = AOI
    date_start = f"{date_str}T00:00:00.000Z"
    date_end = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime(
        "%Y-%m-%dT00:00:00.000Z"
    )
    url = (
        f"{CDSE_CATALOGUE_URL}?"
        f"$filter=Collection/Name eq 'SENTINEL-1' "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S') "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'orbitDirection' "
        f"and att/OData.CSC.StringAttribute/Value eq '{ORBIT_DIRECTION}') "
        f"and ContentDate/Start gt {date_start} "
        f"and ContentDate/Start lt {date_end} "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
        f"{lon_min} {lat_min},{lon_max} {lat_min},"
        f"{lon_max} {lat_max},{lon_min} {lat_max},"
        f"{lon_min} {lat_min}))')"
        f"&$top=5"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json().get("value", [])


def main():
    print("Authenticating with CDSE...")
    token = get_token()
    print(f"Checking {ORBIT_DIRECTION} orbit scenes over Emilia-Romagna AOI\n")

    all_found = True
    for label, date_str in TARGET_DATES.items():
        results = search_scene(date_str, token)
        if results:
            name = results[0]["Name"]
            size_mb = results[0].get("ContentLength", 0) / (1024 * 1024)
            print(f"[OK]      {label} ({date_str}): {name} ({size_mb:.0f} MB)")
        else:
            print(f"[MISSING] {label} ({date_str}): no scene found — try +/-1 day")
            all_found = False

    print()
    if all_found:
        print("Both scenes confirmed. Update pipeline_config.yaml dates if needed, then run:")
        print("  python scripts/run_processing.py")
    else:
        print("Adjust dates in TARGET_DATES above and in pipeline_config.yaml, then retry.")


if __name__ == "__main__":
    main()
