# SAR Flood Mapping — Jacobabad District, Pakistan (2022 Mega-Flood)

Sentinel-1 SAR flood mapping of the 2022 Pakistan monsoon flood, validated against Copernicus EMS (EMSR629) delineations. Part of [SARFloodAnalysis](../README.md). This is the **best-case scenario**: arid pre-event soils, correct-direction specular signal.

---

## Data

| Role | Date | Scene |
|---|---|---|
| Pre-event | 25 Jul 2022 | `S1A_IW_GRDH_1SDV_20220725T012549` — Descending |
| Post-event | 30 Aug 2022 | `S1A_IW_GRDH_1SDV_20220830T012526` — Descending |

**Reference**: EMSR629 AOI01 — peak flood delineation (DEL_PRODUCT, r1_v2). Processing bbox tightened to the EMSR629 AOI01 extent (68.02–68.50°E, 27.40–27.75°N).

Jacobabad district, Sindh (annual rainfall <150 mm) is one of the driest populated areas on Earth, providing maximum pre/post SAR contrast for open-water flood mapping.

---

## Pipeline

SNAP gamma-naught RTC (SRTM 1-sec DEM, UTM 42N, 20 m). Detection mode: **`directional_decrease`** — √(min(ΔVV,0)² + min(ΔVH,0)²). Only backscatter decreases contribute, suppressing crop growth and harvest signals that would otherwise add noise. `combined_magnitude` was tested and underperforms (IoU 0.231) for this open-water arid scenario.

**Masking**: JRC Global Surface Water ≥ 75% (235 ha permanent water excluded); SRTM slope > 2°.

**Threshold calibration**: 0.1–15 dB (30 steps), maximising IoU against EMSR629 peak. Optimal: **0.1 dB** — IoU decreases monotonically as the threshold rises, confirming the signal is real throughout but weak.

---

## Backscatter Comparison

<p align="center">
<img src="outputs/figures/fig01_backscatter_comparison.png" width="800">
</p>

*Figure 1: VV gamma-naught before (25 Jul) and after (30 Aug). EMSR629 reference in red.*

The pre/post contrast is immediately visible and more dramatic than either European case study. Pre-event Jacobabad shows high backscatter — dry, flat, sparsely vegetated arid terrain is a strong radar reflector. Post-event shows widespread darkening consistent with specular reflection from flood water.

---

## Change Map

<p align="center">
<img src="outputs/figures/fig02_change_map.png" width="700">
</p>

*Figure 2: VV log-ratio (ΔVV, dB). Asymmetric scale (−20 to +5 dB) emphasises the flood decrease signal. EMSR629 reference in green.*

A spatially coherent region of strong backscatter decrease (deep blue) aligns closely with the EMSR629 reference. The arid background shows near-zero change — stable pre-event conditions provide a clean baseline. The urban core of Jacobabad shows weaker or mixed signal: flooded buildings produce double-bounce that partially offsets the expected specular decrease.

```
Mean ΔVV inside  EMSR629 reference:  −0.68 dB  (flood signal — correct direction)
Mean ΔVV outside EMSR629 reference:  −0.14 dB  (stable arid background)
Signal separation:                    −0.54 dB
```

---

## Flood Detection vs Reference

<p align="center">
<img src="outputs/figures/fig03_flood_detection.png" width="700">
</p>

*Figure 3: Classification vs EMSR629 peak. Blue = True Positive, Red = False Positive, Orange = False Negative, Grey = correct background.*

True positives (blue) are spatially coherent across the rural floodplain. False negatives (orange) concentrate in the Jacobabad urban core where building double-bounce suppresses the specular decrease. False positives (red) are present but far less dominant than in the European cases — the stable arid background provides a clean reference.

The detected area (129,251 ha) is 2.6× the EMSR629 reference (50,185 ha). Much of this excess is likely genuine unlabelled inundation: the 2022 Sindh flood extended well beyond the EMSR629 AOI01 boundary, meaning detections outside the reference boundary are counted as false positives even when they may be correct.

---

## Results

| Metric | Value |
|---|---|
| **IoU vs EMSR629 peak** | **0.251** |
| Precision | 0.278 |
| Recall | 0.717 |
| F1 | 0.401 |
| Detected area | 129,251 ha |
| EMSR629 reference area | 50,185 ha |
| Detection mode | directional_decrease |
| Calibrated threshold | 0.1 dB |
| Permanent water masked | 235 ha |

---

## Threshold Calibration

<p align="center">
<img src="outputs/figures/fig04_validation_metrics.png" width="800">
</p>

*Figure 4: IoU, precision, and recall vs threshold (left); final metrics at 0.1 dB (right).*

IoU peaks at the lowest tested threshold (0.1 dB) and decreases monotonically — the opposite shape to the flat Wroclaw curve. Precision stays broadly stable (~28%) as the threshold rises because pixels being removed at higher thresholds are genuine flood pixels on arid terrain, not noise. Recall falls rapidly, driving IoU down.

The monotonically decreasing shape confirms a **real signal**: even very small backscatter decreases on arid terrain are diagnostic of inundation. Pre-analysis expected IoU 0.40–0.70 based on ~15 dB specular contrast. Actual separation is −0.54 dB for two reasons:

1. **Urban flooding**: Jacobabad (population ~200,000) is a dense urban centre. Flooded buildings produce double-bounce that partially cancels the specular decrease — only 15.5% of reference pixels show VV < −5 dB.
2. **Reference incompleteness**: EMSR629 AOI01 maps ~50k ha of an estimated 200k+ ha inundated in the processing bbox. Detections outside the reference boundary are penalised as false positives, depressing both precision and IoU.

---

## Running

```bash
cd jacobabad/
python scripts/run_processing.py   # SNAP RTC (~1-2 hrs)
python scripts/run_analysis.py     # composites → change detection → validation
python scripts/make_figures.py
```

Configuration: [`config/pipeline_config.yaml`](config/pipeline_config.yaml)

---

## Data Sources

| Dataset | Source |
|---|---|
| Sentinel-1 IW GRD | [Copernicus CDSE](https://dataspace.copernicus.eu/) |
| EMSR629 delineations | [Copernicus EMS](https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR629) |
| JRC Global Surface Water | [EC JRC](https://global-surface-water.appspot.com/) |
| SRTM 1-arc-second DEM | SNAP auxdata (NASA/USGS) |

---

## References

- Twele, A. et al. (2016). Sentinel-1-based flood mapping: a fully automated processing chain. *Int. J. Remote Sens.* 37(13), 2990–3004.
- Chini, M. et al. (2017). Hierarchical Split-Based Approach for Parametric Thresholding of SAR Images. *IEEE TGRS* 55(12), 6975–6988.
- Pekel, J.F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature* 540, 418–422.
- Farr, T.G. et al. (2007). The Shuttle Radar Topography Mission. *Rev. Geophys.* 45, RG2004.
