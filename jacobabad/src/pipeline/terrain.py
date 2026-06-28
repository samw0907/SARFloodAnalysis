import os
import zipfile
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from rasterio.merge import merge
from io import BytesIO
from src.utils.config import load_config


def read_srtm_tile(zip_path):
    """
    Read one SRTM 1-arc-second HGT tile from a SNAP-format ZIP archive.
    Returns (data, transform, crs) in EPSG:4326.
    """
    base = os.path.basename(zip_path)          # e.g. N44E011.SRTMGL1.hgt.zip
    tile_name = base.split(".")[0]              # e.g. N44E011

    lat = int(tile_name[1:3]) * (1 if tile_name[0] == "N" else -1)
    lon = int(tile_name[4:7]) * (1 if tile_name[3] == "E" else -1)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        match = next((n for n in names if n.endswith(".hgt")), None)
        if match is None:
            raise FileNotFoundError(f"No .hgt file in {zip_path}")
        with zf.open(match) as f:
            raw = f.read()

    # SRTM 1-sec: 3601×3601 big-endian signed int16
    data = np.frombuffer(raw, dtype=">i2").reshape(3601, 3601).astype(np.float32)
    data[data == -32768] = np.nan

    pixel = 1.0 / 3600.0
    transform = from_origin(lon, lat + 1.0, pixel, pixel)
    crs = rasterio.CRS.from_epsg(4326)

    return data, transform, crs


def compute_slope_degrees(dem_utm, pixel_size_m, smooth_sigma=2.0):
    """
    Compute slope in degrees from a UTM-projected DEM.
    Applies Gaussian smoothing (sigma in pixels) before gradient to suppress
    SRTM noise and coastal edge artifacts. Standard practice for slope-based
    flood mapping (Copernicus EMS uses smoothed DEM for terrain filtering).
    """
    from scipy.ndimage import gaussian_filter

    valid = ~np.isnan(dem_utm)
    dem_filled = np.where(valid, dem_utm, 0.0)

    # Smooth to remove SRTM 1-arc-sec noise (~±5m accuracy → inflated slopes)
    if smooth_sigma > 0:
        dem_smooth = gaussian_filter(dem_filled.astype(np.float64), sigma=smooth_sigma)
        # Restore nodata to smoothed version where original was nodata
        dem_smooth[~valid] = np.nan
    else:
        dem_smooth = dem_filled.astype(np.float64)
        dem_smooth[~valid] = np.nan

    dem_for_grad = np.where(np.isnan(dem_smooth), 0.0, dem_smooth)
    dy, dx = np.gradient(dem_for_grad, pixel_size_m, pixel_size_m)
    slope = np.degrees(np.arctan(np.sqrt(dx ** 2 + dy ** 2)))
    slope[~valid] = np.nan
    return slope


def build_slope_mask(config=None):
    """
    Build a binary slope mask (True = terrain too steep to flood) from SRTM tiles
    cached by SNAP. Saves the result to config paths.terrain_slope_mask and also
    returns the mask array.

    Returns: (mask, profile) where mask is boolean (True = steep = exclude).
    """
    if config is None:
        config = load_config()

    srtm_dir = config["terrain"]["srtm_dir"]
    slope_threshold = config["terrain"].get("slope_threshold_deg", 2.0)
    out_path = config["terrain"]["slope_mask"]
    spacing = config["processing"]["spacing"]
    target_crs = rasterio.CRS.from_epsg(config["processing"]["crs"])

    # Find relevant SRTM tiles (tiles that intersect the processing bbox)
    bbox = config["study_area"].get("processing_bbox", config["study_area"]["combined_bbox"])
    lon_min, lat_min, lon_max, lat_max = bbox

    needed = set()
    for lat in range(int(lat_min), int(lat_max) + 1):
        for lon in range(int(lon_min), int(lon_max) + 1):
            lat_str = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            lon_str = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            needed.add(f"{lat_str}{lon_str}")

    # Locate cached ZIP files
    tile_datasets = []
    for tile_name in sorted(needed):
        pattern = f"{tile_name}.SRTMGL1.hgt.zip"
        zip_path = os.path.join(srtm_dir, pattern)
        if not os.path.exists(zip_path):
            print(f"  WARNING: SRTM tile not found: {zip_path} — skipping")
            continue

        data, transform, crs = read_srtm_tile(zip_path)
        profile = {
            "driver": "GTiff", "dtype": "float32",
            "count": 1, "crs": crs, "transform": transform,
            "width": data.shape[1], "height": data.shape[0],
            "nodata": np.nan,
        }
        # Write to in-memory file for merge
        buf = BytesIO()
        with rasterio.open(buf, "w", **profile) as dst:
            dst.write(data[np.newaxis, :, :])
        buf.seek(0)
        tile_datasets.append(rasterio.open(buf))

    if not tile_datasets:
        raise RuntimeError("No SRTM tiles found — check terrain.srtm_dir in config")

    print(f"  Merging {len(tile_datasets)} SRTM tiles...")
    mosaic, mosaic_transform = merge(tile_datasets)
    mosaic = mosaic[0].astype(np.float32)
    mosaic[mosaic == -32768] = np.nan
    for ds in tile_datasets:
        ds.close()

    # Determine target grid from existing composite (matches change rasters exactly)
    composite_path = os.path.join(
        config.get("paths", {}).get("rtc_output", "data/rtc"),
        "..",
        "analysis",
        "change_vv.tif",
    )
    composite_path = os.path.normpath(composite_path)

    if os.path.exists(composite_path):
        with rasterio.open(composite_path) as ref:
            dst_transform = ref.transform
            dst_width = ref.width
            dst_height = ref.height
    else:
        # Fallback: compute from bbox and spacing
        from rasterio.warp import transform_bounds
        left, bottom, right, top = transform_bounds(
            "EPSG:4326", target_crs,
            lon_min, lat_min, lon_max, lat_max,
        )
        dst_transform = rasterio.transform.from_bounds(
            left, bottom, right, top,
            int((right - left) / spacing),
            int((top - bottom) / spacing),
        )
        dst_width = int((right - left) / spacing)
        dst_height = int((top - bottom) / spacing)

    print(f"  Reprojecting DEM to EPSG:{config['processing']['crs']} at {spacing}m...")
    dem_utm = np.full((dst_height, dst_width), np.nan, dtype=np.float32)

    src_profile = {
        "crs": rasterio.CRS.from_epsg(4326),
        "transform": mosaic_transform,
        "count": 1, "dtype": "float32",
        "nodata": np.nan,
    }
    with rasterio.MemoryFile() as memfile:
        with memfile.open(driver="GTiff", height=mosaic.shape[0],
                          width=mosaic.shape[1], count=1,
                          dtype="float32", crs=src_profile["crs"],
                          transform=src_profile["transform"], nodata=np.nan) as src_ds:
            src_ds.write(mosaic, 1)
            reproject(
                source=rasterio.band(src_ds, 1),
                destination=dem_utm,
                src_transform=mosaic_transform,
                src_crs=rasterio.CRS.from_epsg(4326),
                dst_transform=dst_transform,
                dst_crs=target_crs,
                resampling=Resampling.bilinear,
                src_nodata=np.nan,
                dst_nodata=np.nan,
            )

    print(f"  Computing slope (threshold: {slope_threshold}°)...")
    slope = compute_slope_degrees(dem_utm, spacing)

    # True where terrain is too steep to flood (should be excluded)
    steep_mask = slope > slope_threshold
    steep_mask[np.isnan(slope)] = True  # exclude nodata areas

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    profile = {
        "driver": "GTiff", "dtype": "uint8", "count": 1,
        "crs": target_crs, "transform": dst_transform,
        "width": dst_width, "height": dst_height,
        "compress": "lzw",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(steep_mask.astype(np.uint8), 1)

    print(f"  Slope mask written: {out_path}")
    steep_pct = steep_mask.mean() * 100
    print(f"  {steep_pct:.1f}% of scene excluded as too steep (>{slope_threshold}°)")

    return steep_mask, profile


def load_slope_mask(config, target_transform, target_shape):
    """
    Load the pre-computed slope mask and align it to the target raster grid.
    Returns boolean array (True = steep = exclude from flood detection).
    """
    mask_path = config["terrain"]["slope_mask"]
    if not os.path.exists(mask_path):
        raise FileNotFoundError(
            f"Slope mask not found at {mask_path}. "
            "Run scripts/prepare_terrain.py first."
        )

    h, w = target_shape
    aligned = np.zeros((h, w), dtype=np.uint8)
    dst_crs = rasterio.CRS.from_epsg(config["processing"]["crs"])

    with rasterio.open(mask_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=aligned,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
        )

    return aligned.astype(bool)
