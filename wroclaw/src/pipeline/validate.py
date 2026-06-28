# src/pipeline/validate.py
import os
import json
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
import geopandas as gpd
import yaml
from src.utils.config import load_config
from src.pipeline.change import (
    apply_flood_mask, remove_small_patches,
    load_composite, clip_to_bbox, load_jrc_water_mask,
    compute_log_ratio, vectorise_mask, write_mask
)


def load_reference(path, target_crs):
    """
    Load EMSR756 reference flood extent shapefile.
    Filters to event_type == '5-Flood' if column exists.
    Some EMSR756 products contain only geometry with no attributes.
    Reprojects to target CRS.
    """
    gdf = gpd.read_file(path)
    if "event_type" in gdf.columns:
        gdf = gdf[gdf["event_type"] == "5-Flood"].copy()
    return gdf.to_crs(target_crs)


def rasterise_reference(ref_gdf, target_profile):
    """
    Convert EMSR756 reference flood polygons to a binary raster
    aligned to our flood mask grid.
    Returns binary array: 1 = reference flood, 0 = no flood.
    """
    if len(ref_gdf) == 0:
        print("  WARNING: No reference flood polygons found")
        return np.zeros(
            (target_profile["height"], target_profile["width"]), dtype=np.uint8
        )

    shapes = [(geom, 1) for geom in ref_gdf.geometry]
    ref_raster = rasterize(
        shapes,
        out_shape=(target_profile["height"], target_profile["width"]),
        transform=target_profile["transform"],
        fill=0,
        dtype=np.uint8,
    )
    return ref_raster


def compute_metrics(pred, ref):
    """
    Compute pixel-level validation metrics between predicted and reference
    binary flood masks.

    Returns dict of:
    - IoU (Intersection over Union) — primary metric for flood extent comparison
    - Precision, Recall, F1
    - TP, FP, FN, TN pixel counts
    - Detected area and reference area in hectares (at 20m = 400m2 per pixel)
    """
    tp = int(np.sum((pred == 1) & (ref == 1)))
    fp = int(np.sum((pred == 1) & (ref == 0)))
    fn = int(np.sum((pred == 0) & (ref == 1)))
    tn = int(np.sum((pred == 0) & (ref == 0)))

    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    pixel_area_ha = 400 / 10000  # 20m x 20m pixel = 400m2 = 0.04 ha

    return {
        "iou": round(iou, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "detected_area_ha": round((tp + fp) * pixel_area_ha, 1),
        "reference_area_ha": round((tp + fn) * pixel_area_ha, 1),
    }


def calibrate_threshold(
    change_vv, change_vh, ref_raster, permanent_water,
    min_pixels, threshold_range=(1.0, 12.0), steps=30
):
    """
    Sweep combined magnitude thresholds to find the IoU-maximising value.
    Uses the maximum flood extent reference as the calibration target.

    Thresholds are positive — flood detected where combined magnitude
    sqrt(VV² + VH²) exceeds threshold. Captures both open water (negative VV)
    and flooded vegetation double-bounce (positive VH) signals.

    Returns:
        optimal_threshold  float
        best_metrics       dict
        sweep_results      list of {threshold, iou, precision, recall}
        best_mask          numpy array
    """
    thresholds = np.linspace(threshold_range[0], threshold_range[1], steps)

    sweep_results = []
    for t in thresholds:
        mask = apply_flood_mask(change_vv, change_vh, t, permanent_water)
        mask = remove_small_patches(mask, min_pixels)
        metrics = compute_metrics(mask, ref_raster)
        sweep_results.append({
            "threshold": round(float(t), 3),
            "iou": metrics["iou"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "detected_area_ha": metrics["detected_area_ha"],
        })

    best = max(sweep_results, key=lambda x: x["iou"])
    optimal_threshold = best["threshold"]

    # Recompute full metrics at optimal threshold
    best_mask = apply_flood_mask(change_vv, change_vh, optimal_threshold, permanent_water)
    best_mask = remove_small_patches(best_mask, min_pixels)
    best_metrics = compute_metrics(best_mask, ref_raster)

    return optimal_threshold, best_metrics, sweep_results, best_mask

def update_config_threshold(threshold, config_path="config/pipeline_config.yaml"):
    """Write calibrated threshold back to pipeline config."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    config["change_detection"]["threshold_db"] = round(float(threshold), 3)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"  Calibrated threshold written to config: {threshold} dB")


def run_validation(config=None):
    """
    Main validation function.

    Validates our detected flood extent against three EMSR756 reference products:
    - Peak flood (18 Sep 2024) — observedEventA from DEL_PRODUCT
    - Recession (21 Sep 2024) — observedEventA from DEL_MONIT01
    - Maximum extent (full event) — maximumFloodExtentA from DEL_MONIT01

    Calibrates threshold against maximum extent reference (most complete),
    writes calibrated threshold back to config, saves validation summary JSON.
    """
    if config is None:
        config = load_config()

    analysis_dir = os.path.join("data", "analysis")
    validation_dir = os.path.join("data", "validation")
    os.makedirs(validation_dir, exist_ok=True)

    target_crs = f"EPSG:{config['processing']['crs']}"
    jrc_path = os.path.join("data", "external", "jrc_water_wroclaw.tif")
    jrc_threshold = config["permanent_water"]["jrc_occurrence_threshold"]
    pixel_area_ha = (config["processing"]["spacing"] ** 2) / 10000
    min_pixels = int(0.5 / pixel_area_ha)

    # Load composites and recompute change arrays for threshold sweep
    print("Loading composites for threshold calibration...")
    pre_vv, profile = load_composite(
        os.path.join(analysis_dir, "pre_composite_VV.tif")
    )
    post_vv, _ = load_composite(
        os.path.join(analysis_dir, "post_composite_VV.tif")
    )
    pre_vh, _ = load_composite(
        os.path.join(analysis_dir, "pre_composite_VH.tif")
    )
    post_vh, _ = load_composite(
        os.path.join(analysis_dir, "post_composite_VH.tif")
    )

    # Crop to minimum common shape
    min_rows = min(pre_vv.shape[0], post_vv.shape[0])
    min_cols = min(pre_vv.shape[1], post_vv.shape[1])
    pre_vv = pre_vv[:min_rows, :min_cols]
    post_vv = post_vv[:min_rows, :min_cols]
    pre_vh = pre_vh[:min_rows, :min_cols]
    post_vh = post_vh[:min_rows, :min_cols]
    profile.update(width=min_cols, height=min_rows)

    change_vv = compute_log_ratio(pre_vv, post_vv)
    change_vh = compute_log_ratio(pre_vh, post_vh)

    # Clip to processing bbox
    processing_bbox = config["study_area"].get(
        "processing_bbox", config["study_area"]["combined_bbox"]
    )
    change_vv_clipped, clipped_profile = clip_to_bbox(
        change_vv, profile, processing_bbox
    )
    change_vh_clipped, _ = clip_to_bbox(change_vh, profile, processing_bbox)

    # Load permanent water mask
    permanent_water = load_jrc_water_mask(
        jrc_path, clipped_profile, jrc_threshold
    )

    # Load and rasterise all three reference products
    print("\nLoading EMSR756 reference products...")
    ref_paths = {
        "peak":     config["validation"]["emsr_peak"],
        "recession": config["validation"]["emsr_recession"],
        "maximum":  config["validation"]["emsr_maximum"],
    }

    ref_rasters = {}
    ref_areas = {}
    for name, path in ref_paths.items():
        print(f"  Loading {name} reference: {os.path.basename(path)}")
        ref_gdf = load_reference(path, target_crs)
        ref_raster = rasterise_reference(ref_gdf, clipped_profile)
        ref_rasters[name] = ref_raster
        ref_areas[name] = round(
            float(ref_gdf.to_crs(target_crs).geometry.area.sum()) / 10000, 1
        )
        print(f"  {name}: {len(ref_gdf)} polygons, {ref_areas[name]:.0f} ha")

    # Calibrate threshold against maximum flood extent
    # Use wider sweep range — combined magnitude in this vegetated floodplain
    # event is high across the scene due to seasonal agricultural change.
    # Sweep up to 15 dB to find the IoU peak.
    print(f"\nCalibrating threshold against maximum flood extent reference...")
    print(f"Sweeping thresholds from 1.0 dB to 15.0 dB (30 steps)...")

    optimal_threshold, best_metrics, sweep_results, best_mask = calibrate_threshold(
        change_vv_clipped, change_vh_clipped,
        ref_rasters["maximum"], permanent_water,
        min_pixels,
        threshold_range=(1.0, 15.0),
        steps=30
    )

    print(f"\nOptimal threshold: {optimal_threshold} dB")
    print(f"IoU vs maximum extent:  {best_metrics['iou']}")
    print(f"Precision:              {best_metrics['precision']}")
    print(f"Recall:                 {best_metrics['recall']}")
    print(f"Detected area:          {best_metrics['detected_area_ha']} ha")
    print(f"Reference area:         {best_metrics['reference_area_ha']} ha")

    # Write calibrated flood mask
    write_mask(
        best_mask, clipped_profile,
        os.path.join(analysis_dir, "flood_mask_calibrated.tif")
    )

    # Vectorise calibrated mask
    flood_gdf = vectorise_mask(best_mask, clipped_profile)
    vectors_dir = os.path.join("data", "vectors")
    os.makedirs(vectors_dir, exist_ok=True)
    flood_gdf.to_file(
        os.path.join(vectors_dir, "flood_extent_calibrated.geojson"),
        driver="GeoJSON"
    )

    # Compute metrics at calibrated threshold against all three references
    print("\nComputing metrics against all reference products...")
    all_metrics = {}
    for name, ref_raster in ref_rasters.items():
        m = compute_metrics(best_mask, ref_raster)
        m["reference_name"] = name
        m["reference_area_ha"] = ref_areas[name]
        m["threshold_db"] = optimal_threshold
        all_metrics[name] = m
        print(f"  vs {name}: IoU={m['iou']}, Precision={m['precision']}, "
              f"Recall={m['recall']}, Detected={m['detected_area_ha']} ha")

    # Write calibrated threshold back to config
    current_threshold = config["change_detection"]["threshold_db"]
    if optimal_threshold != current_threshold:
        update_config_threshold(optimal_threshold)
    else:
        print(f"  Threshold unchanged at {current_threshold} dB")

    # Write validation summary JSON
    summary = {
        "calibrated_threshold_db": optimal_threshold,
        "calibration_reference": "maximum",
        "detection_mode": "combined_magnitude",
        "reference_areas_ha": ref_areas,
        "metrics": all_metrics,
        "threshold_sweep": sweep_results,
        "permanent_water_pixels": int(permanent_water.sum())
        if permanent_water is not None else 0,
        "permanent_water_ha": round(
            int(permanent_water.sum()) * pixel_area_ha, 1
        ) if permanent_water is not None else 0,
    }

    summary_path = os.path.join(validation_dir, "validation_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nValidation summary written: {summary_path}")

    return summary, flood_gdf


if __name__ == "__main__":
    summary, flood_gdf = run_validation()
    print(f"\nCalibrated threshold: {summary['calibrated_threshold_db']} dB")
    for name, m in summary["metrics"].items():
        print(f"{name}: IoU={m['iou']}, F1={m['f1']}, "
              f"Detected={m['detected_area_ha']} ha")


if __name__ == "__main__":
    summary, flood_gdf = run_validation()
    print(f"\nCalibrated threshold: {summary['calibrated_threshold_db']} dB")
    for name, m in summary["metrics"].items():
        print(f"{name}: IoU={m['iou']}, F1={m['f1']}, "
              f"Detected={m['detected_area_ha']} ha")