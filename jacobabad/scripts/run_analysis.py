# scripts/run_analysis.py
# Full analysis pipeline: composites -> terrain prep -> change detection -> validation.
# Run from project root: python -m scripts.run_analysis

import os
from src.pipeline.composite import run_composites
from src.pipeline.change import run_change_detection
from src.pipeline.validate import run_validation
from src.utils.config import load_config

config = load_config()

print("=== STEP 1: COMPOSITES ===")
run_composites()

print()
print("=== STEP 2: TERRAIN PREPARATION ===")
slope_mask_path = config.get("terrain", {}).get("slope_mask", "")
if slope_mask_path and not os.path.exists(slope_mask_path):
    from src.pipeline.terrain import build_slope_mask
    build_slope_mask(config)
else:
    print(f"  Slope mask already exists: {slope_mask_path}")

print()
print("=== STEP 3: CHANGE DETECTION ===")
run_change_detection(config)

print()
print("=== STEP 4: VALIDATION ===")
summary, _ = run_validation(config)

print()
print("=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
print(f"Detection mode:      {summary.get('detection_mode', 'directional_decrease')}")
print(f"Threshold:           {summary['calibrated_threshold_db']} dB")
print(f"Calibrated against:  {summary['calibration_reference']}")
print(f"Permanent water:     {summary['permanent_water_ha']} ha")
print(f"Terrain excluded:    {summary.get('terrain_excluded_ha', 0)} ha")
print()
for name, m in summary["metrics"].items():
    print(f"{name.upper()}:")
    print(f"  IoU={m['iou']}  Precision={m['precision']}  Recall={m['recall']}  F1={m['f1']}")
    print(f"  Detected={m['detected_area_ha']} ha  Reference={m['reference_area_ha']} ha")
