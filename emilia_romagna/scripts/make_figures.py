"""
scripts/make_figures.py
Generate publication-quality figures for the Emilia-Romagna SAR flood mapping study.

Run: python -m scripts.make_figures
Outputs: outputs/figures/fig0[1-4]_*.png (300 DPI)
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import rasterio
from rasterio.plot import reshape_as_image
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
import geopandas as gpd
from src.utils.config import load_config

# ─────────────────────────────── helpers ────────────────────────────────────

def read_aoi_window(path, bounds_utm, crs_utm):
    """Read a raster clipped to bounds_utm (left,bottom,right,top in UTM)."""
    with rasterio.open(path) as src:
        window = from_bounds(*bounds_utm, transform=src.transform)
        data = src.read(1, window=window)
        win_transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(width=data.shape[1], height=data.shape[0],
                       transform=win_transform)
    return data.astype(np.float32), win_transform, profile


def percentile_stretch(data, lo=2, hi=98):
    """Clip data to percentile range and normalise to 0-1."""
    valid = data[np.isfinite(data)]
    vmin = np.percentile(valid, lo)
    vmax = np.percentile(valid, hi)
    stretched = np.clip(data, vmin, vmax)
    return (stretched - vmin) / (vmax - vmin + 1e-9)


def add_scalebar(ax, transform, length_km=10, loc="lower right"):
    """Add a simple scale bar (only valid for UTM projections)."""
    px_m = abs(transform.a)  # metres per pixel
    px_len = length_km * 1000 / px_m

    ax_w = ax.get_xlim()[1] - ax.get_xlim()[0]
    ax_h = ax.get_ylim()[1] - ax.get_ylim()[0]

    if "right" in loc:
        x0 = ax.get_xlim()[1] - 0.05 * ax_w - px_len
    else:
        x0 = ax.get_xlim()[0] + 0.05 * ax_w

    if "lower" in loc:
        y0 = ax.get_ylim()[0] + 0.05 * ax_h
    else:
        y0 = ax.get_ylim()[1] - 0.08 * ax_h

    ax.plot([x0, x0 + px_len], [y0, y0], "k-", lw=3, solid_capstyle="butt")
    ax.text(x0 + px_len / 2, y0 + 0.02 * ax_h,
            f"{length_km} km", ha="center", va="bottom", fontsize=8, color="k")


def rasterise_ref(ref_gdf, aoi_profile):
    """Rasterise an EMSR GeoDataFrame onto the AOI grid."""
    from rasterio.features import rasterize
    shapes = [(geom, 1) for geom in ref_gdf.geometry if geom is not None]
    if not shapes:
        return np.zeros((aoi_profile["height"], aoi_profile["width"]), dtype=np.uint8)
    return rasterize(
        shapes,
        out_shape=(aoi_profile["height"], aoi_profile["width"]),
        transform=aoi_profile["transform"],
        fill=0, dtype=np.uint8,
    )


def save_fig(fig, name, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {path}")


# ─────────────────────────────── main ───────────────────────────────────────

def main():
    config = load_config()
    OUT = os.path.join("outputs", "figures")
    os.makedirs(OUT, exist_ok=True)

    target_crs = f"EPSG:{config['processing']['crs']}"
    processing_bbox = config["study_area"].get("processing_bbox",
                                                config["study_area"]["combined_bbox"])
    lon_min, lat_min, lon_max, lat_max = processing_bbox
    bounds_utm = transform_bounds("EPSG:4326", CRS.from_epsg(config["processing"]["crs"]),
                                  lon_min, lat_min, lon_max, lat_max)

    # ── load rasters ──────────────────────────────────────────────────────
    print("Loading rasters...")
    pre_vv,  pre_t,  pre_p  = read_aoi_window("data/analysis/pre_composite_VV.tif",
                                               bounds_utm, target_crs)
    post_vv, post_t, post_p = read_aoi_window("data/analysis/post_composite_VV.tif",
                                               bounds_utm, target_crs)
    chg_vv,  chg_t,  chg_p  = read_aoi_window("data/analysis/change_vv.tif",
                                               bounds_utm, target_crs)

    with rasterio.open("data/analysis/flood_mask_calibrated.tif") as src:
        flood_mask = src.read(1)
        flood_t = src.transform
        flood_p = src.profile.copy()
        flood_bounds = src.bounds  # these ARE already the AOI bounds

    # rasterio extent tuples for imshow: (left, right, bottom, top)
    def extent(t, shape):
        h, w = shape
        return (t.c, t.c + w * t.a, t.f + h * t.e, t.f)

    pre_ext  = extent(pre_t,  pre_vv.shape)
    post_ext = extent(post_t, post_vv.shape)
    chg_ext  = extent(chg_t,  chg_vv.shape)
    flood_ext = (flood_bounds.left, flood_bounds.right,
                 flood_bounds.bottom, flood_bounds.top)

    # ── load EMSR reference shapefiles ────────────────────────────────────
    print("Loading EMSR reference shapefiles...")
    peak_path = config["validation"]["emsr_peak"]
    rec_path  = config["validation"]["emsr_recession"]

    peak_gdf = gpd.read_file(peak_path).to_crs(target_crs)
    rec_gdf  = gpd.read_file(rec_path).to_crs(target_crs)

    if "event_type" in peak_gdf.columns:
        peak_gdf = peak_gdf[peak_gdf["event_type"] == "5-Flood"]
    if "event_type" in rec_gdf.columns:
        rec_gdf = rec_gdf[rec_gdf["event_type"] == "5-Flood"]

    peak_r = rasterise_ref(peak_gdf, flood_p)
    rec_r  = rasterise_ref(rec_gdf,  flood_p)

    # ── load validation summary ────────────────────────────────────────────
    with open("data/validation/validation_summary.json") as f:
        val = json.load(f)

    # ─────────────────────────────────────────────────────────────────────
    # Figure 1: Pre-event vs Post-event SAR backscatter (VV)
    # ─────────────────────────────────────────────────────────────────────
    print("Figure 1: Backscatter comparison...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.suptitle("Sentinel-1 VV Backscatter: Emilia-Romagna May 2023",
                 fontsize=13, fontweight="bold", y=0.98)

    # Shared stretch limits
    all_vals = np.concatenate([
        pre_vv[np.isfinite(pre_vv)].ravel(),
        post_vv[np.isfinite(post_vv)].ravel()
    ])
    vmin, vmax = np.percentile(all_vals, 2), np.percentile(all_vals, 98)

    for ax, data, ext, title, date in [
        (axes[0], pre_vv,  pre_ext,  "Pre-event",  "10 May 2023"),
        (axes[1], post_vv, post_ext, "Post-event", "22 May 2023"),
    ]:
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

    add_scalebar(axes[1], post_t, length_km=10)
    plt.subplots_adjust(right=0.87, wspace=0.05, top=0.90, bottom=0.10, left=0.06)
    cbar_ax = fig.add_axes([0.89, 0.12, 0.02, 0.73])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label("VV Backscatter (dB)", fontsize=9)
    save_fig(fig, "fig01_backscatter_comparison.png", OUT)

    # ─────────────────────────────────────────────────────────────────────
    # Figure 2: VV Change map
    # ─────────────────────────────────────────────────────────────────────
    print("Figure 2: Change map...")
    fig, ax = plt.subplots(figsize=(10, 7))

    # Symmetric ±10 dB around zero, diverging colourmap
    cmap_div = plt.cm.RdBu_r
    clim = 10.0
    im = ax.imshow(chg_vv, cmap=cmap_div, vmin=-clim, vmax=clim,
                   extent=chg_ext, origin="upper")

    ax.set_title("VV Backscatter Change (Post − Pre)\nEmilia-Romagna Floods, May 2023",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))
    ax.tick_params(labelsize=8)

    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("ΔVV (dB)  ← decrease  |  increase →", fontsize=9)
    add_scalebar(ax, chg_t, length_km=10)
    plt.tight_layout()
    save_fig(fig, "fig02_change_map.png", OUT)

    # ─────────────────────────────────────────────────────────────────────
    # Figure 3: Flood detection vs reference
    # ─────────────────────────────────────────────────────────────────────
    print("Figure 3: Flood detection...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.suptitle("SAR Flood Detection vs EMSR Reference",
                 fontsize=13, fontweight="bold", y=1.01)

    # Build TP/FP/FN composite arrays (relative to peak ref)
    # 0=background, 1=TP, 2=FP, 3=FN
    composite = np.zeros_like(flood_mask, dtype=np.uint8)
    composite[peak_r == 1] = 3           # all ref = FN initially
    composite[(flood_mask == 1) & (peak_r == 0)] = 2   # FP
    composite[(flood_mask == 1) & (peak_r == 1)] = 1   # TP

    colors_det = ["#f0f0f0", "#1a7abf", "#e34a33", "#fdae61"]
    labels_det = ["Background", "True Positive", "False Positive", "False Negative"]
    cmap_det = LinearSegmentedColormap.from_list("det", colors_det, N=4)

    # ── detection vs peak ──────────────────────────────────────────────
    ax = axes[0]
    ax.imshow(composite, cmap=cmap_det, vmin=0, vmax=3,
              extent=flood_ext, origin="upper")
    ax.set_title("vs Peak Flood\n(EMSR664 DEL_PRODUCT)", fontsize=10)
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))
    ax.tick_params(labelsize=7)

    m_pk = val["metrics"].get("peak", {})
    ax.text(0.02, 0.97,
            f"IoU = {m_pk.get('iou', 0):.3f}\n"
            f"Precision = {m_pk.get('precision', 0):.3f}\n"
            f"Recall = {m_pk.get('recall', 0):.3f}\n"
            f"F1 = {m_pk.get('f1', 0):.3f}\n"
            f"Detected = {m_pk.get('detected_area_ha', 0):.0f} ha\n"
            f"Reference = {m_pk.get('reference_area_ha', 0):.0f} ha",
            transform=ax.transAxes, va="top", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    # ── detection vs recession ─────────────────────────────────────────
    composite_r = np.zeros_like(flood_mask, dtype=np.uint8)
    composite_r[rec_r == 1] = 3
    composite_r[(flood_mask == 1) & (rec_r == 0)] = 2
    composite_r[(flood_mask == 1) & (rec_r == 1)] = 1

    ax = axes[1]
    im2 = ax.imshow(composite_r, cmap=cmap_det, vmin=0, vmax=3,
                    extent=flood_ext, origin="upper")
    ax.set_title("vs Recession Flood\n(EMSR664 DEL_MONIT01)", fontsize=10)
    ax.set_xlabel("Easting (m)")
    ax.ticklabel_format(style="sci", axis="both", scilimits=(6, 6))
    ax.tick_params(labelsize=7)

    m_re = val["metrics"].get("recession", {})
    ax.text(0.02, 0.97,
            f"IoU = {m_re.get('iou', 0):.3f}\n"
            f"Precision = {m_re.get('precision', 0):.3f}\n"
            f"Recall = {m_re.get('recall', 0):.3f}\n"
            f"F1 = {m_re.get('f1', 0):.3f}\n"
            f"Detected = {m_re.get('detected_area_ha', 0):.0f} ha\n"
            f"Reference = {m_re.get('reference_area_ha', 0):.0f} ha",
            transform=ax.transAxes, va="top", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    patches = [mpatches.Patch(color=c, label=l)
               for c, l in zip(colors_det, labels_det)]
    axes[1].legend(handles=patches, loc="lower right", fontsize=7,
                   framealpha=0.85, edgecolor="gray")

    # Zoom into the EMSR reference extent so sparse TP/FP/FN pixels are visible.
    # The full processing area is much larger than the flood extent.
    ref_bounds = peak_gdf.total_bounds  # [minx, miny, maxx, maxy]
    margin_m = 10000  # 10 km margin
    for ax in axes:
        ax.set_xlim(ref_bounds[0] - margin_m, ref_bounds[2] + margin_m)
        ax.set_ylim(ref_bounds[1] - margin_m, ref_bounds[3] + margin_m)

    add_scalebar(axes[0], flood_t, length_km=5)
    add_scalebar(axes[1], flood_t, length_km=5)
    plt.tight_layout()
    save_fig(fig, "fig03_flood_detection.png", OUT)

    # ─────────────────────────────────────────────────────────────────────
    # Figure 4: Threshold sweep + metrics bar chart
    # ─────────────────────────────────────────────────────────────────────
    print("Figure 4: Validation metrics...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Change Detection Calibration and Validation Metrics",
                 fontsize=12, fontweight="bold")

    # ── threshold sweep ────────────────────────────────────────────────
    sweep = val["threshold_sweep"]
    thresholds = [s["threshold"] for s in sweep]
    ious      = [s["iou"] for s in sweep]
    precs     = [s["precision"] for s in sweep]
    recs      = [s["recall"] for s in sweep]

    ax1.plot(thresholds, ious,  "b-o", ms=4, lw=1.5, label="IoU")
    ax1.plot(thresholds, precs, "g--s", ms=4, lw=1.2, label="Precision")
    ax1.plot(thresholds, recs,  "r--^", ms=4, lw=1.2, label="Recall")

    opt_t = val["calibrated_threshold_db"]
    opt_iou = val["metrics"].get(val["calibration_reference"], {}).get("iou", 0)
    ax1.axvline(opt_t, color="purple", ls=":", lw=1.5,
                label=f"Optimal = {opt_t} dB")
    ax1.axhline(opt_iou, color="purple", ls=":", lw=1)

    ax1.set_xlabel("Change Magnitude Threshold (dB)", fontsize=10)
    ax1.set_ylabel("Score", fontsize=10)
    ax1.set_title(f"Threshold Calibration\n(calibrated against {val['calibration_reference']})", fontsize=10)
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, None)
    ax1.grid(True, alpha=0.3)

    # ── metrics bar chart ──────────────────────────────────────────────
    refs = list(val["metrics"].keys())
    metric_names = ["iou", "precision", "recall", "f1"]
    n_refs = len(refs)
    x = np.arange(len(metric_names))
    width = 0.35

    colours = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"][:n_refs]

    for i, ref in enumerate(refs):
        m = val["metrics"][ref]
        values = [m.get(k, 0) for k in metric_names]
        offset = (i - n_refs / 2 + 0.5) * width
        bars = ax2.bar(x + offset, values, width=width * 0.9,
                       label=ref.capitalize(), color=colours[i], alpha=0.85)
        for bar, v in zip(bars, values):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                     f"{v:.3f}", ha="center", va="bottom", fontsize=7)

    ax2.set_xticks(x)
    ax2.set_xticklabels([m.upper() for m in metric_names], fontsize=9)
    ax2.set_ylabel("Score", fontsize=10)
    ax2.set_title("Validation Metrics vs EMSR References", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.set_ylim(0, max(0.4, ax2.get_ylim()[1]))
    ax2.grid(True, axis="y", alpha=0.3)
    ax2.axhline(0.5, color="gray", ls="--", lw=0.8, alpha=0.5)

    plt.tight_layout()
    save_fig(fig, "fig04_validation_metrics.png", OUT)

    print(f"\nAll figures saved to: {os.path.abspath(OUT)}")
    print(f"  fig01_backscatter_comparison.png")
    print(f"  fig02_change_map.png")
    print(f"  fig03_flood_detection.png")
    print(f"  fig04_validation_metrics.png")


if __name__ == "__main__":
    main()
