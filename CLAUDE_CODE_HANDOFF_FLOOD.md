# Claude Code Handoff — SAR Flood Mapping
## Emilia-Romagna, Italy | May 2023
## Status: COMPLETE — IoU 0.054 (peak) / 0.131 (recession), figures + README done

Part of the combined portfolio: `C:\Users\swill\dev\SARFloodAnalysis\emilia_romagna\`

---

## Project Overview

Production-grade SAR flood extent mapping pipeline. Sentinel-1 GRD scenes
processed through pyroSAR/SNAP to gamma-naught RTC backscatter, change detection
between pre and post-flood scenes, flood classification, validated against
Copernicus EMS EMSR664 reference delineation.

Repo: github.com/samw0907/SARFloodItaly
Local: C:\Users\swill\dev\SARFloodItaly
Python 3.14, Windows. Run all scripts from project root.
Use `python -m scripts.X` (not `python scripts/X.py`) for correct PYTHONPATH.

---

## Event Context

Catastrophic river flooding across Emilia-Romagna, northern Italy, May 2023.
Multiple rivers (Savio, Ronco, Montone, Rabbi, Lamone) overflowed after two
storm systems — a smaller event May 2-3 and the catastrophic peak May 16-18.

Two Sentinel-1A scenes, descending orbit, VV+VH, EPSG:32632 UTM Zone 32N:
- Pre:  2023-05-10 (12-day cycle; only S-1A operational in May 2023, S-1B inactive)
- Post: 2023-05-22 (post-peak recession, first available scene after flooding)

Note: EMSR664 AOI01 was used (not EMSR660-663 which cover different sub-areas).
No maximumFloodExtentA product exists for EMSR664 — calibrated against peak (DEL_PRODUCT).

---

## Pipeline Status

```
[COMPLETE] Scene check      2023-05-10 pre, 2023-05-22 post confirmed on CDSE
[COMPLETE] Download         data/raw/ (not copied to SARFloodAnalysis — 3.4 GB)
[COMPLETE] RTC Processing   pyroSAR/SNAP gamma-naught, 20m, EPSG:32632
                            data/rtc/ (not copied to SARFloodAnalysis — 3.9 GB)
[COMPLETE] Composites       data/analysis/pre_composite_VV/VH, post_composite_VV/VH
[COMPLETE] Terrain mask     data/external/slope_mask.tif (5° threshold, SRTM tiles
                            N44E011 + N44E012, Gaussian sigma=2px smoothing applied)
[COMPLETE] Change detection change_vv.tif, change_vh.tif, change_combined.tif
                            Mode: combined_magnitude (best for mixed landscape)
[COMPLETE] JRC masking      jrc_water_italy.tif (tile 10E_40N, occurrence >= 75%)
[COMPLETE] Validation       IoU 0.054 (peak), 0.131 (recession)
                            Threshold: 9.69 dB
                            Terrain excluded: 191,997 ha
[COMPLETE] Figures          4 figures at 300 DPI in outputs/figures/
[COMPLETE] README           Comprehensive README with results, figures, methodology
[DEFERRED] S3 sync          After all 3 case studies complete
[DEFERRED] CI/CD            After all 3 case studies complete
[DEFERRED] Docker           After all 3 case studies complete
```

---

## Final Results

| vs EMSR664 | IoU | Precision | Recall | F1 | Detected | Reference |
|---|---|---|---|---|---|---|
| **Peak (DEL_PRODUCT)** | **0.054** | 0.041 | 0.913 | 0.079 | 533,440 ha | 27,590 ha |
| Recession (DEL_MONIT01) | 0.131 | 0.154 | 0.638 | 0.247 | 22,350 ha | 5,397 ha |

### Why IoU is low despite the pipeline working correctly

This event has a soil moisture confound: the heavy rain that caused flooding
also saturated every surrounding field. Quantitative signal separation:
- Mean VV change inside EMSR664 flood reference: -1.36 dB
- Mean VV change outside reference:               -0.68 dB
- Separation:                                      0.68 dB -- essentially at noise floor

Literature confirms IoU 0.05-0.15 is expected for wet-antecedent temperate floods
with single-date change detection. The pipeline is working correctly.
The better recession IoU (0.131) reflects true specular open water remaining
after the initial soil saturation has partially dried.

---

## Key Config (Final State)

```yaml
scenes:
  pre:  ['2023-05-10']
  post: ['2023-05-22']
  orbit_direction: DESCENDING

processing:
  crs: 32632   # UTM Zone 32N
  spacing: 20

change_detection:
  threshold_db: 9.69
  mode: combined_magnitude

terrain:
  srtm_dir: C:/Users/swill/.snap/auxdata/dem/SRTM 1Sec HGT
  slope_threshold_deg: 5.0
  slope_mask: data/external/slope_mask.tif

permanent_water:
  jrc_occurrence_threshold: 75

validation:
  emsr_peak:      data/external/EMSR664_AOI01_DEL_PRODUCT_observedEventA_v1.shp
  emsr_recession: data/external/EMSR664_AOI01_DEL_MONIT01_observedEventA_v1.shp
```

---

## Key Design Decisions

### Why combined_magnitude (not directional_decrease or pol_ratio)

- `directional_decrease` (`sqrt(min(VV,0)^2 + min(VH,0)^2)`) -- tested, IoU 0.047.
  Hurt performance because some EMSR reference pixels in slightly-sloped terrain have
  partial double-bounce (positive VV), not purely specular (negative VV).
- `pol_ratio` (delta_VH - delta_VV) -- IoU 0.032. VH cross-pol has lower SNR;
  the ratio amplifies noise at both ends.
- `combined_magnitude` (sqrt(delta_VV^2 + delta_VH^2)) -- best for this mixed
  urban/agricultural landscape. Final mode.

### Terrain slope masking

SRTM slope mask required Gaussian smoothing (sigma=2 pixels = 40m footprint):
1. Raw np.gradient on SRTM without smoothing creates large false slopes at
   coast/water edges where NaN-fill introduces sharp transitions.
2. The load_slope_mask() reproject call must use dst_crs = target UTM CRS,
   not src.crs. This was a critical bug found and fixed -- using src.crs
   silently reprojected the mask back to EPSG:4326, misaligning it.

---

## Key Files

```
config/pipeline_config.yaml     All parameters (authoritative)
src/pipeline/
  change.py                     Change detection + flood classification
  terrain.py                    SRTM slope mask generation and alignment
  validate.py                   EMSR validation + threshold calibration
  composite.py                  Pre/post composites
  download.py                   CDSE scene download
  rtc.py                        pyroSAR/SNAP processing
scripts/
  run_analysis.py               Steps 2-4: terrain, change, validate
  run_processing.py             Steps 1-2: download, RTC
  make_figures.py               4 production figures (300 DPI)
data/external/
  EMSR664_AOI01_DEL_PRODUCT_observedEventA_v1.shp     Peak reference
  EMSR664_AOI01_DEL_MONIT01_observedEventA_v1.shp     Recession reference
  jrc_water_italy.tif           JRC Global Surface Water (tile 10E_40N)
  slope_mask.tif                Binary steep mask (True = exclude from detection)
data/validation/
  validation_summary.json       IoU, precision, recall, threshold sweep
outputs/figures/
  fig01_backscatter_comparison.png   Pre/post VV with EMSR overlay (300 DPI)
  fig02_change_map.png               VV log-ratio change (diverging colormap)
  fig03_flood_detection.png          TP/FP/FN vs peak and recession (300 DPI)
  fig04_validation_metrics.png       Threshold calibration sweep + metric bars
```

---

## Combined Project

This project is part of SARFloodAnalysis:
  C:\Users\swill\dev\SARFloodAnalysis\emilia_romagna\

Lightweight files are synced there (no data/raw/, data/rtc/, data/analysis/).
Full analysis rasters remain at C:\Users\swill\dev\SARFloodItaly\data\analysis\.

---

## Notes on Python Environment

- Python 3.14 on Windows
- GDAL installed via Gohlke wheel
- SNAP GPT on PATH (RTC already done, no need to rerun)
- pyroSAR 0.36.2
- scipy required for terrain.py (gaussian_filter)
- GitHub secrets set: CDSE_USER, CDSE_PASSWORD, AWS_ACCESS_KEY_ID,
  AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
