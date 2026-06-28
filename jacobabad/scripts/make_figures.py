"""
scripts/make_figures.py — Jacobabad District, Pakistan 2022
Generate publication-quality figures from existing analysis outputs.
Run: python -m scripts.make_figures   (from jacobabad/ root)
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
import geopandas as gpd
from src.utils.config import load_config


# ─────── helpers ──────────────────────────────────────────────────────────────

def read_aoi_window(path, bounds_utm):
    with rasterio.open(path) as src:
        window = from_bounds(*bounds_utm, transform=src.transform)
        data = src.read(1, window=window)
        win_transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(width=data.shape[1], height=data.shape[0],
                       transform=win_transform)
    return data.astype(np.float32), win_transform, profile


def rasterise_ref(ref_gdf, aoi_profile):
    from rasterio.features import rasterize
    shapes = [(g, 1) for g in ref_gdf.geometry if g is not None]
    if not shapes:
        return np.zeros((aoi_profile["height"], aoi_profile["width"]), dtype=np.uint8)
    return rasterize(shapes,
                     out_shape=(aoi_profile["height"], aoi_profile["width"]),
                     transform=aoi_profile["transform"],
                     fill=0, dtype=np.uint8)


def extent_from(transform, shape):
    h, w = shape
    return (transform.c, transform.c + w * transform.a,
            transform.f + h * transform.e, transform.f)


def add_scalebar(ax, transform, length_km=25):
    px_m = abs(transform.a)
    px_len = length_km * 1000 / px_m
    ax_w = ax.get_xlim()[1] - ax.get_xlim()[0]
    ax_h = ax.get_ylim()[1] - ax.get_ylim()[0]
    x0 = ax.get_xlim()[1] - 0.05 * ax_w - px_len
    y0 = ax.get_ylim()[0] + 0.05 * ax_h
    ax.plot([x0, x0 + px_len], [y0, y0], "k-", lw=3, solid_capstyle="butt")
    ax.text(x0 + px_len / 2, y0 + 0.02 * ax_h, f"{length_km} km",
            ha="center", va="bottom", fontsize=8)


def save_fig(fig, name, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {path}")


# ─────── main ─────────────────────────────────────────────────────────────────

def main():
    config = load_config()
    OUT = os.path.join("outputs", "figures")
    target_crs = f"EPSG:{config['processing']['crs']}"
    processing_bbox = config["study_area"].get("processing_bbox",
                                                config["study_area"]["combined_bbox"])
    lon_min, lat_min, lon_max, lat_max = processing_bbox
    bounds_utm = transform_bounds("EPSG:4326", CRS.from_epsg(config["processing"]["crs"]),
                                  lon_min, lat_min, lon_max, lat_max)

    pre_dates  = config["scenes"]["pre"]
    post_dates = config["scenes"]["post"]
    pre_label  = pre_dates[0] if pre_dates else "pre-event"
    post_label = post_dates[0] if post_dates else "post-event"

    print("Loading rasters...")
    pre_vv,  pre_t,  _     = read_aoi_window("data/analysis/pre_composite_VV.tif",  bounds_utm)
    post_vv, post_t, _     = read_aoi_window("data/analysis/post_composite_VV.tif", bounds_utm)
    chg_vv,  chg_t,  _     = read_aoi_window("data/analysis/change_vv.tif",         bounds_utm)

    with rasterio.open("data/analysis/flood_mask_calibrated.tif") as src:
        flood_mask = src.read(1)
        flood_t    = src.transform
        flood_p    = src.profile.copy()
        flood_ext  = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)

    print("Loading EMSR629 peak reference...")
    peak_path = config["validation"]["emsr_peak"]
    peak_gdf = gpd.read_file(peak_path).to_crs(target_crs)
    if "event_type" in peak_gdf.columns:
        peak_gdf = peak_gdf[peak_gdf["event_type"].str.contains("Flood", case=False, na=False)]
    print(f"  peak: {len(peak_gdf)} polygons, {peak_gdf.geometry.area.sum()/1e4:.0f} ha")

    peak_r = rasterise_ref(peak_gdf, flood_p)

    with open("data/validation/validation_summary.json") as f:
        val = json.load(f)

    # ── Figure 1: Pre vs Post SAR backscatter ────────────────────────────────
    print("Figure 1: Backscatter comparison...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.suptitle("Sentinel-1 VV Backscatter: Jacobabad District Floods — Pakistan, Aug 2022",
                 fontsize=12, fontweight="bold", y=0.98)

    all_v = np.concatenate([pre_vv[np.isfinite(pre_vv)].ravel(),
                            post_vv[np.isfinite(post_vv)].ravel()])
    vmin, vmax = np.percentile(all_v, 2), np.percentile(all_v, 98)

    for ax, data, t, title, date in [
        (axes[0], pre_vv,  pre_t,  "Pre-event (dry baseline)", pre_label),
        (axes[1], post_vv, post_t, "Post-event (peak flood)",  post_label),
    ]:
        ext = extent_from(t, data.shape)
        im = ax.imshow(data, cmap="gray", vmin=vmin, vmax=vmax, extent=ext, origin="upper")
        ax.set_title(f"{title}\n{date}", fontsize=11)
        ax.set_xlabel("Easting (m)")
        ax.tick_params(labelsize=7)
        ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))

    axes[0].set_ylabel("Northing (m)")
    # Force both panels to the same geographic extent (processing bbox)
    for ax in axes:
        ax.set_xlim(bounds_utm[0], bounds_utm[2])
        ax.set_ylim(bounds_utm[1], bounds_utm[3])
    add_scalebar(axes[1], post_t, length_km=25)
    plt.subplots_adjust(right=0.87, wspace=0.05, top=0.90, bottom=0.10, left=0.06)
    cbar_ax = fig.add_axes([0.89, 0.12, 0.02, 0.73])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label("VV Backscatter (dB)", fontsize=9)
    save_fig(fig, "fig01_backscatter_comparison.png", OUT)

    # ── Figure 2: VV Change map ───────────────────────────────────────────────
    print("Figure 2: Change map...")
    fig, ax = plt.subplots(figsize=(10, 8))
    chg_ext = extent_from(chg_t, chg_vv.shape)
    # Pakistan flood: strong VV decrease expected — use asymmetric stretch to highlight it
    im = ax.imshow(chg_vv, cmap="RdBu_r", vmin=-20, vmax=5,
                   extent=chg_ext, origin="upper")
    ax.set_title("VV Backscatter Change (Post − Pre)\n"
                 "Jacobabad Floods — Pakistan, Jul–Aug 2022",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))
    ax.tick_params(labelsize=8)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("ΔVV (dB)  ← strong decrease (flood)  |  increase →", fontsize=9)
    add_scalebar(ax, chg_t, length_km=25)
    plt.tight_layout()
    save_fig(fig, "fig02_change_map.png", OUT)

    # ── Figure 3: Flood detection vs peak reference ───────────────────────────
    print("Figure 3: Flood detection...")
    colors_det = ["#f0f0f0", "#1a7abf", "#e34a33", "#fdae61"]
    labels_det = ["Background", "True Positive", "False Positive", "False Negative"]
    cmap_det = LinearSegmentedColormap.from_list("det", colors_det, N=4)

    comp = np.zeros_like(flood_mask, dtype=np.uint8)
    comp[peak_r == 1] = 3
    comp[(flood_mask == 1) & (peak_r == 0)] = 2
    comp[(flood_mask == 1) & (peak_r == 1)] = 1

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(comp, cmap=cmap_det, vmin=0, vmax=3, extent=flood_ext, origin="upper")
    ax.set_title("SAR Flood Detection vs EMSR629 Reference\n"
                 "Jacobabad District — Pakistan 2022",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))
    ax.tick_params(labelsize=8)

    m = val["metrics"].get("peak", {})
    ax.text(0.02, 0.97,
            f"IoU = {m.get('iou', 0):.3f}\n"
            f"Precision = {m.get('precision', 0):.3f}\n"
            f"Recall = {m.get('recall', 0):.3f}\n"
            f"F1 = {m.get('f1', 0):.3f}\n"
            f"Detected = {m.get('detected_area_ha', 0):.0f} ha\n"
            f"Reference = {m.get('reference_area_ha', 0):.0f} ha",
            transform=ax.transAxes, va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    patches = [mpatches.Patch(color=c, label=l)
               for c, l in zip(colors_det, labels_det)]
    ax.legend(handles=patches, loc="lower right", fontsize=8,
              framealpha=0.85, edgecolor="gray")
    add_scalebar(ax, flood_t, length_km=25)
    plt.tight_layout()
    save_fig(fig, "fig03_flood_detection.png", OUT)

    # ── Figure 4: Threshold sweep + metrics bar ───────────────────────────────
    print("Figure 4: Validation metrics...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Change Detection Calibration and Validation Metrics — Pakistan 2022",
                 fontsize=12, fontweight="bold")

    sweep = val.get("threshold_sweep", [])
    if sweep:
        thresholds = [s["threshold"] for s in sweep]
        ax1.plot(thresholds, [s["iou"] for s in sweep],      "b-o",  ms=4, lw=1.5, label="IoU")
        ax1.plot(thresholds, [s["precision"] for s in sweep], "g--s", ms=4, lw=1.2, label="Precision")
        ax1.plot(thresholds, [s["recall"] for s in sweep],    "r--^", ms=4, lw=1.2, label="Recall")
        opt_t   = val["calibrated_threshold_db"]
        opt_iou = val["metrics"].get(val.get("calibration_reference", "peak"), {}).get("iou", 0)
        ax1.axvline(opt_t,   color="purple", ls=":", lw=1.5, label=f"Optimal = {opt_t} dB")
        ax1.axhline(opt_iou, color="purple", ls=":", lw=1)
    ax1.set_xlabel("Threshold (dB)", fontsize=10)
    ax1.set_ylabel("Score", fontsize=10)
    ax1.set_title(f"Threshold Calibration (directional decrease mode)", fontsize=10)
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, None)
    ax1.grid(True, alpha=0.3)

    metric_names = ["iou", "precision", "recall", "f1"]
    x = np.arange(len(metric_names))
    m = val["metrics"].get("peak", {})
    vals = [m.get(k, 0) for k in metric_names]
    bars = ax2.bar(x, vals, 0.5, color="#2196F3", alpha=0.85, label="Peak (EMSR629)")
    for bar, v in zip(bars, vals):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.005,
                 f"{v:.3f}", ha="center", va="bottom", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([k.upper() for k in metric_names], fontsize=9)
    ax2.set_ylabel("Score", fontsize=10)
    ax2.set_title("Validation Metrics vs EMSR629 Reference", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.5, color="gray", ls="--", lw=0.8, alpha=0.5, label="0.5 benchmark")
    ax2.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    save_fig(fig, "fig04_validation_metrics.png", OUT)

    print(f"\nAll figures saved to: {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
