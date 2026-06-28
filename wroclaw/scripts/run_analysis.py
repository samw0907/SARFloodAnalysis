# scripts/run_analysis.py
# Full analysis pipeline: composites -> change detection -> validation.
# Run from project root: python scripts/run_analysis.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.composite import run_composites
from src.pipeline.change import run_change_detection
from src.pipeline.validate import run_validation
from src.utils.config import load_config

config = load_config()

print("=== STEP 1: COMPOSITES ===")
run_composites()

print()
print("=== STEP 2: CHANGE DETECTION ===")
run_change_detection(config)

print()
print("=== STEP 3: VALIDATION ===")
summary, _ = run_validation(config)

print()
print("=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
print(f"Detection mode:      {summary.get('detection_mode', 'combined_magnitude')}")
print(f"Threshold:           {summary['calibrated_threshold_db']} dB")
print(f"Calibrated against:  {summary['calibration_reference']}")
print(f"Permanent water:     {summary['permanent_water_ha']} ha")
print()
for name, m in summary["metrics"].items():
    print(f"{name.upper()}:")
    print(f"  IoU={m['iou']}  Precision={m['precision']}  Recall={m['recall']}  F1={m['f1']}")
    print(f"  Detected={m['detected_area_ha']} ha  Reference={m['reference_area_ha']} ha")
