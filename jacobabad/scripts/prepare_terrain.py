# scripts/prepare_terrain.py
# Generates the slope mask from SNAP-cached SRTM tiles.
# Run once before run_analysis.py: python -m scripts.prepare_terrain

from src.pipeline.terrain import build_slope_mask
from src.utils.config import load_config

config = load_config()
print("Building slope mask from SRTM tiles...")
build_slope_mask(config)
print("Done.")
