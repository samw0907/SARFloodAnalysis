# scripts/check_scenes.py
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv("config/.env")

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

BBOX = [67.8, 27.2, 68.7, 28.0]
ORBIT = "DESCENDING"

DATES = {
    "pre":  "2022-07-25",
    "post": "2022-08-30",
}


def get_token():
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": os.getenv("CDSE_USER"),
            "password": os.getenv("CDSE_PASSWORD"),
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search(date_str, token):
    lon_min, lat_min, lon_max, lat_max = BBOX
    date_end = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime(
        "%Y-%m-%dT00:00:00.000Z"
    )
    url = (
        f"{CATALOGUE_URL}?"
        f"$filter=Collection/Name eq 'SENTINEL-1' "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S') "
        f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'orbitDirection' "
        f"and att/OData.CSC.StringAttribute/Value eq '{ORBIT}') "
        f"and ContentDate/Start gt {date_str}T00:00:00.000Z "
        f"and ContentDate/Start lt {date_end} "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
        f"{lon_min} {lat_min},{lon_max} {lat_min},"
        f"{lon_max} {lat_max},{lon_min} {lat_max},"
        f"{lon_min} {lat_min}))')"
        f"&$top=3"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json().get("value", [])


def main():
    print("Authenticating with CDSE...")
    token = get_token()
    print(f"Checking {ORBIT} orbit scenes over Jacobabad AOI\n")

    all_found = True
    for label, date in DATES.items():
        results = search(date, token)
        if results:
            print(f"[OK] {label} ({date}): {results[0]['Name']}")
        else:
            print(f"[MISSING] {label} ({date}): no scene found")
            all_found = False

    print()
    if all_found:
        print("Both scenes confirmed. Safe to proceed with download.")
    else:
        print("WARNING: Some scenes missing. Adjust dates and retry.")


if __name__ == "__main__":
    main()