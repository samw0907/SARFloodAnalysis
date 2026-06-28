# src/pipeline/change.py
import os
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform_bounds, reproject, Resampling
from rasterio.windows import from_bounds
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from src.utils.config import load_config


def load_composite(path):
    """Load a composite GeoTIFF and return array and profile."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
    return data, profile


def compute_log_ratio(pre, post):
    """
    Compute log-ratio change in dB space.
    Negative values = backscatter decrease = flood signal.
    """
    return post - pre


def load_jrc_water_mask(jrc_path, target_profile, occurrence_threshold=75):
    """
    Load JRC Global Surface Water occurrence raster and create a binary
    permanent water mask aligned to the target raster grid.
    Pixels with water occurrence > threshold are classified as permanent water.
    Returns binary mask: 1 = permanent water, 0 = not permanent water.
    """
    if not os.path.exists(jrc_path):
        print(f"  WARNING: JRC water mask not found at {jrc_path} — skipping permanent water masking")
        return None

    print(f"  Loading JRC permanent water mask (threshold: {occurrence_threshold}%)...")

    target_height = target_profile["height"]
    target_width = target_profile["width"]
    target_transform = target_profile["transform"]
    target_crs = target_profile["crs"]

    water_mask = np.zeros((target_height, target_width), dtype=np.uint8)

    with rasterio.open(jrc_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=water_mask,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest,
        )

    permanent_water = (water_mask >= occurrence_threshold).astype(np.uint8)
    n_pixels = int(permanent_water.sum())
    print(f"  Permanent water pixels: {n_pixels} ({n_pixels * 400 / 10000:.0f} ha)")
    return permanent_water


def apply_flood_mask(change_vv, change_vh, threshold_db, permanent_water_mask=None):
    """
    Classify flooded pixels based on combined VV+VH change magnitude.

    For this event (Storm Boris, riverine flood through vegetated floodplain),
    the dominant signal is POSITIVE — flooded vegetation produces double-bounce
    (water surface + plant stems) increasing backscatter in VH. Open water
    produces negative VV change. Combined magnitude captures both signals.

    A pixel is classified as flooded if:
    - combined magnitude >= threshold (large change in either direction)
    - AND it is not classified as permanent water

    Returns binary flood mask: 1 = flooded, 0 = not flooded.
    """
    combined = np.sqrt(change_vv**2 + change_vh**2)

    flood_mask = np.zeros_like(combined, dtype=np.uint8)
    flood_mask[combined >= threshold_db] = 1

    if permanent_water_mask is not None:
        flood_mask[permanent_water_mask == 1] = 0

    flood_mask[np.isnan(combined)] = 0

    return flood_mask


def remove_small_patches(mask, min_pixels):
    """
    Remove isolated pixel groups smaller than min_pixels using rasterio
    sieve filter. GDAL/C-level implementation — correct tool for geospatial
    raster operations at this scale. Methodology identical to connected
    component labelling but orders of magnitude faster on large arrays.
    Connectivity=4 (cardinal directions only, standard for flood mapping).
    """
    from rasterio.features import sieve
    return sieve(mask.astype(np.uint8), size=min_pixels, connectivity=4)


def clip_to_bbox(array, profile, bbox_lonlat):
    """
    Clip a raster array to a bounding box in lon/lat (EPSG:4326).
    Returns clipped array and updated profile.
    """
    src_crs = profile["crs"]
    transform = profile["transform"]

    lon_min, lat_min, lon_max, lat_max = bbox_lonlat
    left, bottom, right, top = transform_bounds(
        CRS.from_epsg(4326), src_crs,
        lon_min, lat_min, lon_max, lat_max
    )

    window = from_bounds(left, bottom, right, top, transform)
    window = window.round_lengths().round_offsets()

    col_off = max(0, int(window.col_off))
    row_off = max(0, int(window.row_off))
    col_end = min(array.shape[1], col_off + int(window.width))
    row_end = min(array.shape[0], row_off + int(window.height))

    clipped = array[row_off:row_end, col_off:col_end]

    new_transform = transform * rasterio.transform.Affine.translation(col_off, row_off)
    new_profile = profile.copy()
    new_profile.update(
        width=clipped.shape[1],
        height=clipped.shape[0],
        transform=new_transform
    )

    return clipped, new_profile


def vectorise_mask(mask, profile):
    """
    Convert binary flood mask to GeoDataFrame of flood polygons with area in hectares.
    """
    transform = profile["transform"]
    crs = profile["crs"]

    polygons = []
    for geom, val in shapes(mask, transform=transform):
        if val == 1:
            polygons.append(shape(geom))

    if not polygons:
        return gpd.GeoDataFrame(columns=["geometry", "area_ha"], crs=crs)

    gdf = gpd.GeoDataFrame(geometry=polygons, crs=crs)
    gdf["area_ha"] = gdf.geometry.area / 10000
    return gdf


def write_raster(array, profile, output_path):
    """Write a numpy array to GeoTIFF."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_profile = profile.copy()
    out_profile.update(dtype=rasterio.float32, count=1, nodata=np.nan)
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(array.astype(np.float32), 1)


def write_mask(array, profile, output_path):
    """Write a binary uint8 mask to GeoTIFF."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_profile = profile.copy()
    out_profile.update(dtype=rasterio.uint8, count=1, nodata=0)
    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(array.astype(np.uint8), 1)


def run_change_detection(config=None):
    """
    Main change detection function for flood mapping.
    Computes VV and VH log-ratio change, combines into magnitude,
    applies permanent water mask, classifies flood pixels,
    removes small patches, vectorises.
    Returns dict of output paths and flood GeoDataFrame.
    """
    if config is None:
        config = load_config()

    analysis_dir = os.path.join("data", "analysis")
    threshold_db = config["change_detection"]["threshold_db"]
    jrc_threshold = config["permanent_water"]["jrc_occurrence_threshold"]
    jrc_path = os.path.join("data", "external", "jrc_water_wroclaw.tif")

    # Minimum patch size: 0.5 ha at 20m = 12 pixels (400m²/pixel → 0.5ha/0.04ha = 12.5)
    pixel_area_ha = (config["processing"]["spacing"] ** 2) / 10000
    min_pixels = int(0.5 / pixel_area_ha)

    print("Loading composites...")
    pre_vv, profile = load_composite(os.path.join(analysis_dir, "pre_composite_VV.tif"))
    post_vv, _ = load_composite(os.path.join(analysis_dir, "post_composite_VV.tif"))
    pre_vh, _ = load_composite(os.path.join(analysis_dir, "pre_composite_VH.tif"))
    post_vh, _ = load_composite(os.path.join(analysis_dir, "post_composite_VH.tif"))

    # Crop to minimum common shape
    min_rows = min(pre_vv.shape[0], post_vv.shape[0], pre_vh.shape[0], post_vh.shape[0])
    min_cols = min(pre_vv.shape[1], post_vv.shape[1], pre_vh.shape[1], post_vh.shape[1])
    pre_vv  = pre_vv[:min_rows, :min_cols]
    post_vv = post_vv[:min_rows, :min_cols]
    pre_vh  = pre_vh[:min_rows, :min_cols]
    post_vh = post_vh[:min_rows, :min_cols]
    profile.update(width=min_cols, height=min_rows)

    print("Computing change detection...")
    change_vv = compute_log_ratio(pre_vv, post_vv)
    change_vh = compute_log_ratio(pre_vh, post_vh)

    # Write full swath change rasters
    print("Writing change rasters...")
    write_raster(change_vv, profile, os.path.join(analysis_dir, "change_vv.tif"))
    write_raster(change_vh, profile, os.path.join(analysis_dir, "change_vh.tif"))

    # Combined magnitude — captures both open water (negative VV) and
    # flooded vegetation double-bounce (positive VH) signals
    combined_full = np.sqrt(change_vv**2 + change_vh**2)
    write_raster(combined_full, profile,
                 os.path.join(analysis_dir, "change_combined.tif"))

    # Clip to AOI before masking
    print("Clipping to AOI...")
    combined_bbox = config["study_area"].get("processing_bbox", config["study_area"]["combined_bbox"])
    change_vv_clipped, clipped_profile = clip_to_bbox(change_vv, profile, combined_bbox)
    change_vh_clipped, _ = clip_to_bbox(change_vh, profile, combined_bbox)
    print(f"Clipped array shape: {change_vv_clipped.shape}")

    # Load permanent water mask
    permanent_water = load_jrc_water_mask(jrc_path, clipped_profile, jrc_threshold)

    # Apply flood classification
    print(f"Applying flood mask (combined magnitude threshold: {threshold_db} dB)...")
    flood_mask = apply_flood_mask(
        change_vv_clipped, change_vh_clipped,
        threshold_db, permanent_water
    )

    # Remove small patches
    flood_mask = remove_small_patches(flood_mask, min_pixels)

    # Write flood mask
    write_mask(flood_mask, clipped_profile, os.path.join(analysis_dir, "flood_mask.tif"))

    # Vectorise
    print("Vectorising flood extent...")
    flood_gdf = vectorise_mask(flood_mask, clipped_profile)
    total_area = flood_gdf["area_ha"].sum()
    print(f"Total detected flood area: {total_area:.1f} ha across {len(flood_gdf)} patches")

    vectors_dir = os.path.join("data", "vectors")
    os.makedirs(vectors_dir, exist_ok=True)
    flood_path = os.path.join(vectors_dir, "flood_extent.geojson")
    flood_gdf.to_file(flood_path, driver="GeoJSON")
    print(f"Written: {flood_path}")

    outputs = {
        "change_vv": os.path.join(analysis_dir, "change_vv.tif"),
        "change_vh": os.path.join(analysis_dir, "change_vh.tif"),
        "change_combined": os.path.join(analysis_dir, "change_combined.tif"),
        "flood_mask": os.path.join(analysis_dir, "flood_mask.tif"),
        "flood_extent": flood_path,
        "flood_gdf": flood_gdf,
        "total_area_ha": total_area,
    }

    print("\nChange detection complete.")
    return outputs


if __name__ == "__main__":
    outputs = run_change_detection()
    print(f"\nTotal flood area: {outputs['total_area_ha']:.1f} ha")
    print(f"Patch count: {len(outputs['flood_gdf'])}")