# scripts/check_scenes.py
# Checks Sentinel-1 scene availability on CDSE for target dates over Wroclaw AOI.
# Run this before starting the pipeline to confirm all scenes are available.

import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv("config/.env")

CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

# Wroclaw AOI bounding box
AOI = [16.8, 50.8, 17.8, 51.5]  # lon_min, lat_min, lon_max, lat_max

# Target dates to check — adjust if needed
TARGET_DATES = {
    "pre_1":  "2024-08-22",
    "pre_2":  "2024-09-03",
    "post_1": "2024-09-15",
    "post_2": "2024-09-27",
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
    print(f"Checking {ORBIT_DIRECTION} orbit scenes over Wroclaw AOI\n")

    all_found = True
    for label, date_str in TARGET_DATES.items():
        results = search_scene(date_str, token)
        if results:
            name = results[0]["Name"]
            size_mb = results[0].get("ContentLength", 0) / (1024 * 1024)
            print(f"[OK] {label} ({date_str}): {name} ({size_mb:.0f} MB)")
        else:
            print(f"[MISSING] {label} ({date_str}): no scene found")
            all_found = False

    print()
    if all_found:
        print("All 4 scenes confirmed available. Safe to proceed.")
    else:
        print("WARNING: Some scenes missing. Adjust dates in TARGET_DATES and retry.")


if __name__ == "__main__":
    main()