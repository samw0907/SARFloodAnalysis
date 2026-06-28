# src/pipeline/process.py
import os
from pyroSAR.snap import geocode
from src.utils.config import load_config


def process_scene(scene_path, config):
    """
    Process a single Sentinel-1 GRD scene to gamma-naught RTC backscatter
    GeoTIFF using pyroSAR/SNAP. Skips if output already exists.
    Returns the output directory path.
    """
    outdir = config["paths"]["rtc_output"]
    os.makedirs(outdir, exist_ok=True)

    spacing = config["processing"]["spacing"]
    crs = config["processing"]["crs"]
    polarizations = config["processing"]["polarizations"]
    dem = config["processing"]["dem"]
    snap_aux = config["paths"]["snap_aux"]

    os.environ["SNAP_AUX_PATH"] = snap_aux

    print(f"Processing: {os.path.basename(scene_path)}")

    geocode(
        infile=scene_path,
        outdir=outdir,
        shapefile=None,
        t_srs=crs,
        spacing=spacing,
        polarizations=polarizations,
        scaling="dB",
        removeS1BorderNoise=True,
        removeS1BorderNoiseMethod="pyroSAR",
        removeS1ThermalNoise=True,
        geocoding_type="Range-Doppler",
        terrainFlattening=True,
        demName=dem,
        speckleFilter=False,
        refarea="gamma0",
        export_extra=["localIncidenceAngle"],
        cleanup=True,
    )

    print(f"Processing complete: {os.path.basename(scene_path)}")
    return outdir


def run_processing(inventory, config=None):
    """
    Process all scenes in the inventory dict.
    Returns updated inventory with rtc_dir added per scene.
    """
    if config is None:
        config = load_config()

    print(f"\nProcessing {len(inventory)} scenes...")

    for date_str, info in inventory.items():
        scene_path = info["path"]
        rtc_dir = process_scene(scene_path, config)
        inventory[date_str]["rtc_dir"] = rtc_dir

    print("\nAll scenes processed.")
    return inventory


if __name__ == "__main__":
    config = load_config()
    test_scene = input("Enter path to a downloaded .zip scene: ").strip()
    process_scene(test_scene, config)
