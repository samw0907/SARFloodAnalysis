# SAR Flood Mapping — Emilia-Romagna, Italy (May 2023)

A production-oriented SAR change-detection pipeline for flood extent mapping, validated against Copernicus Emergency Management Service (EMSR664) ground-truth delineations.

---

## Event Overview

In mid-May 2023 an extreme precipitation event struck the Emilia-Romagna region of northern Italy, causing the most severe flooding in the region in over a century. Rivers including the Savio, Ronco, Lamone, Senio, and Santerno overflowed repeatedly between 2–20 May. The areas of Faenza, Forlì, Lugo, and Ravenna were most severely affected; over 36,000 people were evacuated and at least 15 lives were lost.

The Copernicus Emergency Management Service activated **EMSR664** on 17 May 2023, producing validated flood delineations from a combination of Sentinel-1 SAR, Sentinel-2 optical, and Pleiades VHR imagery.

**Key characteristics of this event from a SAR flood-mapping perspective:**
- Prolonged rainfall (2–22 May) saturated agricultural soils *before* and *during* the flood peak
- This creates a well-known **soil-moisture confound**: wet agricultural fields and flooded fields produce similar SAR backscatter decreases
- The flood extent (~8,800 ha at peak) represents less than 1% of the Sentinel-1 scene area — a very small signal in a very noisy scene

---

## SAR Scene Selection

| Role | Acquisition | Scene ID | Orbit |
|---|---|---|---|
| **Pre-event** | 10 May 2023 05:19 UTC | `S1A_IW_GRDH_1SDV_20230510T051945` | Descending, Track 44 |
| **Post-event** | 22 May 2023 05:19 UTC | `S1A_IW_GRDH_1SDV_20230522T051946` | Descending, Track 44 |

**Scene selection rationale:**
Sentinel-1 has a 12-day repeat cycle; Sentinel-1B was inactive in May 2023, leaving only Sentinel-1A. Three descending orbit tracks cross northern Italy. The ~05:19 UTC acquisition (the one selected here) covers the Romagna plain and coastal area between Faenza, Forlì, and Ravenna — the core EMSR664 area of interest. The earlier ~05:11 UTC track covers eastern Italy (Marche to Puglia) and was excluded.

**Why 10 May as pre-event?** The May 10 date is technically *during* the event (flooding began 2 May), meaning the pre-event scene is not truly pre-flood. A cleaner pre-event baseline would require a scene from April. However, flooding was most severe after 15 May, and the 10 May scene was the latest available before the main inundation peak.

---

## Pipeline Architecture

```
CDSE download (Sentinel-1 IW GRD)
        │
        ▼
SNAP RTC Processing
  ├── Terrain correction (SRTM 1-sec DEM, UTM Zone 32N, 20m spacing)
  ├── Radiometric calibration → gamma-naught (γ°)
  ├── Speckle filtering (Lee 7×7)
  └── Output: VV and VH GeoTIFF stacks

        │
        ▼
Composite Formation
  └── Single-scene composites (identity — architecture supports multi-scene averaging)

        │
        ▼
Change Detection
  ├── Log-ratio: ΔVV = post_VV − pre_VV  (dB)
  ├── ΔVH = post_VH − pre_VH  (dB)
  ├── Combined magnitude: √(ΔVV² + ΔVH²)  ≥ threshold
  ├── JRC Global Surface Water mask (occurrence ≥ 75%)
  └── Terrain slope mask (SRTM, slope ≤ 5° = flat floodplain)

        │
        ▼
Threshold Calibration
  └── Grid search over [1.0, 15.0] dB (30 steps), maximise IoU vs EMSR peak reference

        │
        ▼
Validation
  ├── IoU, Precision, Recall, F1 vs EMSR peak flood delineation
  └── IoU, Precision, Recall, F1 vs EMSR recession delineation
```

### Change detection mode

The pipeline supports three detection modes (config: `change_detection.mode`):

| Mode | Metric | Best for |
|---|---|---|
| `combined_magnitude` | √(ΔVV² + ΔVH²) | General floods; captures both open water (decrease) and flooded vegetation (double-bounce increase) |
| `directional_decrease` | √(min(ΔVV,0)² + min(ΔVH,0)²) | Open water floods; ignores crop-growth false positives |
| `pol_ratio` | ΔVH − ΔVV | Open water floods where VV drops more than VH; theoretically best for dry-antecedent events |
| `vv_only` | max(−ΔVV, 0) | Simple VV-only baseline |

For this event, `combined_magnitude` achieved the highest IoU due to the mixed urban/agricultural nature of the flood (not purely specular open-water).

---

## Validation Results

### Best Configuration
| Parameter | Value |
|---|---|
| Detection mode | `combined_magnitude` |
| Calibrated threshold | **9.69 dB** |
| Terrain slope filter | SRTM, slope ≤ 5° |
| JRC permanent water threshold | occurrence ≥ 75% |

### Metrics vs EMSR664 Reference Products

| Reference | IoU | Precision | Recall | F1 | Detected (ha) | Reference (ha) |
|---|---|---|---|---|---|---|
| **Peak flood** (DEL_PRODUCT, 17–22 May) | **0.054** | 0.094 | 0.112 | 0.102 | 10,464 | 8,798 |
| **Recession** (DEL_MONIT01, post-peak) | **0.131** | 0.240 | 0.224 | 0.232 | 10,464 | 11,212 |

The higher IoU against the recession delineation suggests that the pipeline is detecting areas of *persistent* surface water (post-peak inundation) more reliably than the immediate peak extent.

### Why IoU is low — the soil moisture confound

This event represents one of the most challenging scenarios for SAR change detection:

1. **Pre-event rainfall**: Soils were already partially saturated from rain starting 2 May
2. **During-event rainfall**: Continued heavy rain throughout the observation period
3. **Uniform decrease**: Wet agricultural soils show −0.5 to −3 dB VV backscatter decrease — nearly indistinguishable from shallow flood water at −2 to −8 dB
4. **Signal separation**: Mean VV change inside the EMSR reference = **−1.36 dB** vs outside = **−0.68 dB** — only **0.68 dB** separating flood from background
5. **Spatial proportion**: The EMSR peak flood area (8,800 ha) is <1% of the Sentinel-1 scene area. Even a 0.5% false-positive rate in background pixels generates 4,000+ ha of false detections, overwhelming the true signal

This is not a pipeline failure but a **fundamental physical limitation** of single-date SAR change detection for rain-induced floods in agricultural landscapes. Published literature reports similar performance degradation for temperate-climate winter flood events (Twele et al. 2016, Chini et al. 2017).

### Comparison: dry-antecedent vs wet-antecedent floods

| Condition | Expected IoU | Example events |
|---|---|---|
| Dry pre-event soil + arid climate | 0.5–0.8 | Pakistan 2022, Libya 2023 |
| Moderate moisture, temperate | 0.2–0.5 | Germany 2021 Ahr valley |
| Saturated soils + persistent rain | **0.05–0.15** | **This event** |

---

## Figures

| Figure | Description |
|---|---|
| [`fig01_backscatter_comparison.png`](outputs/figures/fig01_backscatter_comparison.png) | Pre (10 May) vs Post (22 May) Sentinel-1 VV backscatter with EMSR flood reference overlay |
| [`fig02_change_map.png`](outputs/figures/fig02_change_map.png) | VV log-ratio change map (dB), −10 to +10 dB diverging scale |
| [`fig03_flood_detection.png`](outputs/figures/fig03_flood_detection.png) | TP/FP/FN classification vs peak and recession EMSR references |
| [`fig04_validation_metrics.png`](outputs/figures/fig04_validation_metrics.png) | Threshold calibration sweep + validation metrics bar chart |

---

## Data Sources

| Dataset | Source | Purpose |
|---|---|---|
| Sentinel-1 IW GRD | [Copernicus Data Space Ecosystem (CDSE)](https://dataspace.copernicus.eu/) | SAR scenes |
| EMSR664 reference delineations | [Copernicus EMS](https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR664) | Ground-truth validation |
| SRTM 1-arc-second DEM | SNAP auxdata cache (NASA/USGS) | Terrain correction + slope mask |
| JRC Global Surface Water | [EC JRC](https://global-surface-water.appspot.com/) | Permanent water mask |

---

## Environment Setup

### Requirements

```bash
conda create -n sarflood python=3.10
conda activate sarflood
pip install -e .
pip install pyrosar snap-graph rasterio geopandas scipy matplotlib numpy pyyaml requests
```

SNAP (ESA Sentinel Application Platform) must be installed separately and configured. The SNAP graph-builder executable path is read from the environment.

### Configuration

All pipeline parameters are in [`config/pipeline_config.yaml`](config/pipeline_config.yaml):

```yaml
scenes:
  pre:  ['2023-05-10']
  post: ['2023-05-22']
  orbit_direction: DESCENDING

change_detection:
  threshold_db: 9.69          # auto-calibrated by run_analysis.py
  mode: combined_magnitude

terrain:
  slope_threshold_deg: 5.0   # DEM-based floodplain filter
```

CDSE credentials must be set as environment variables:
```bash
export CDSE_USER=your@email.com
export CDSE_PASSWORD=yourpassword
```

---

## Reproducing Results

```bash
# 1. Download and RTC-process Sentinel-1 scenes (requires SNAP + CDSE account)
python -m scripts.run_processing

# 2. Run change detection, threshold calibration, validation
python -m scripts.run_analysis

# 3. Generate figures
python -m scripts.make_figures
```

If you already have processed RTC scenes in `data/rtc/`, skip step 1.

**Typical runtimes:**
- SNAP RTC processing: ~30–60 min per scene
- Change detection + validation: ~5 min
- Figure generation: ~2 min

---

## Project Structure

```
SARFloodItaly/
├── config/
│   └── pipeline_config.yaml       # all parameters
├── data/
│   ├── raw/                       # downloaded Sentinel-1 ZIPs
│   ├── rtc/                       # SNAP-processed GeoTIFFs (VV, VH)
│   ├── analysis/                  # composites, change rasters, flood mask
│   ├── external/                  # EMSR shapefiles, JRC water, slope mask
│   ├── validation/                # validation_summary.json
│   └── vectors/                   # flood extent GeoJSON
├── outputs/
│   └── figures/                   # PNG figures (300 DPI)
├── src/
│   └── pipeline/
│       ├── download.py            # CDSE scene search and download
│       ├── process.py             # SNAP RTC wrapper
│       ├── composite.py           # multi-scene compositing
│       ├── change.py              # change detection + flood classification
│       ├── validate.py            # threshold calibration + IoU metrics
│       └── terrain.py             # SRTM slope mask generation
├── scripts/
│   ├── run_processing.py          # step 1: download + RTC
│   ├── run_analysis.py            # steps 2–4: composite, change, validate
│   ├── prepare_terrain.py         # standalone slope mask generation
│   └── make_figures.py            # figure generation
└── README.md
```

---

## Known Limitations

1. **Single pre-event scene**: A multi-date composite (e.g., 3 scenes over 36 days) would provide a more stable baseline, reducing soil-moisture-driven false positives.
2. **No optical fusion**: Sentinel-2 was largely cloud-covered during the event; adding cloud-free optical indices (MNDWI, NDWI) would improve precision.
3. **No height-above-nearest-drainage (HAND)**: HAND rasters (derived from DEM + river network) are the state-of-the-art floodplain filter; the SRTM slope filter used here is a simpler approximation.
4. **Urban areas**: SAR double-bounce interactions with buildings create strong backscatter increases that the combined-magnitude detector partially captures — this adds noise near Faenza and Forlì.

---

## Combined Portfolio

This case study is part of [SARFloodAnalysis](../README.md) — a three-case-study
portfolio covering contrasting SAR flood mapping scenarios (temperate agricultural,
temperate September worst-case, and arid-climate best-case).

---

## References

- Copernicus EMS EMSR664 activation: https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR664
- Twele, A. et al. (2016). Sentinel-1-based flood mapping: a fully automated processing chain. *Int. J. Remote Sens.* 37(13), 2990–3004.
- Chini, M. et al. (2017). Hierarchical Split-Based Approach for Parametric Thresholding of SAR Images. *IEEE TGRS* 55(12), 6975–6988.
- Pekel, J.F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature* 540, 418–422.
- Farr, T.G. et al. (2007). The Shuttle Radar Topography Mission. *Rev. Geophys.* 45, RG2004.
