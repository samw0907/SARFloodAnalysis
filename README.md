# SAR Flood Analysis — Multi-Case-Study Collection

A Sentinel-1 SAR flood mapping pipeline applied to three contrasting flood events. The same core methodology runs across all three, with event-appropriate adaptations, enabling direct comparison of how land cover, soil moisture, and flood mechanism affect detection performance.

---

## Case Studies

| Case Study | Event | Date | Best IoU | Status |
|---|---|---|---|---|
| [Emilia-Romagna](emilia_romagna/) | Italy — Faenza/Forlì floods | May 2023 | **0.117** (recession) | Complete |
| [Wroclaw](wroclaw/) | Poland — Storm Boris | Sep 2024 | **0.029** (maximum extent) | Complete |
| [Jacobabad](jacobabad/) | Pakistan — monsoon mega-flood | Jul–Aug 2022 | **0.370** (peak) | Complete |

The three events span the full performance range for SAR change-detection flood mapping — from the physically inverted Wroclaw case (signal mechanism wrong, IoU 0.029) through Italy's soil moisture confound (IoU 0.057 peak / 0.117 recession) to Jacobabad's best-case arid open-water scenario (IoU 0.370).

---

## Methodology

### Pipeline

All three case studies share the same pipeline:

```
CDSE download → SNAP RTC → Composite → Change Detection → Threshold Calibration → Validation
```

Change detection computes the log-ratio of gamma-naught backscatter between pre- and post-event Sentinel-1 IW GRD scenes:

```
ΔVV = post_VV − pre_VV   (dB)
ΔVH = post_VH − pre_VH   (dB)
```

Three detection modes are implemented, with the choice depending on expected flood physics:

| Mode | Formula | Use case |
|---|---|---|
| `combined_magnitude` | √(ΔVV² + ΔVH²) ≥ T | General — captures open-water and flooded-vegetation signals |
| `directional_decrease` | √(min(ΔVV,0)² + min(ΔVH,0)²) ≥ T | Open-water floods on stable backgrounds — suppresses crop growth |
| `pol_ratio` | ΔVH − ΔVV ≥ T | Theoretically optimal for specular open water; limited by VH noise in practice |

Threshold calibration sweeps 0.1–15 dB in 30 steps, selecting the value that maximises IoU against the primary EMSR reference.

Masking applied before classification:
- **Permanent water**: JRC Global Surface Water occurrence ≥ 75% excluded
- **Steep terrain**: SRTM 1-arc-second slope > configured threshold excluded (where applicable)

### Per-Case Parameters

| Parameter | Emilia-Romagna | Wroclaw | Jacobabad |
|---|---|---|---|
| UTM Zone | 32N | 33N | 42N |
| Detection mode | combined_magnitude | combined_magnitude | directional_decrease |
| Slope filter | 5° | none | 2° |
| Pre / post dates | 10 May / 22 May 2023 | 3 Sep / 15 Sep 2024 | 25 Jul / 30 Aug 2022 |
| EMSR reference | EMSR664 | EMSR756 | EMSR629 |
| Calibration target | peak | maximum extent | peak |

---

## Results

### Summary

| Case Study | Mode | Threshold | Best IoU | Precision | Recall | F1 | Detected | Reference |
|---|---|---|---|---|---|---|---|---|
| Emilia-Romagna | combined_magnitude | 7.807 dB | 0.117 (recession) | 0.169 | 0.273 | 0.209 | 18,058 ha | 11,212 ha |
| Wroclaw | combined_magnitude | 2.931 dB | 0.029 (maximum) | 0.029 | 0.810 | 0.056 | 534,863 ha | 20,161 ha |
| Jacobabad | directional_decrease | 7.807 dB | 0.370 (peak) | 0.414 | 0.777 | 0.540 | 94,350 ha | 50,185 ha |

### Signal Separability

Performance is fundamentally determined by how physically distinct the flood SAR response is from the surrounding background:

| Case | Pre-event soil | Mean ΔVV inside flood | Mean ΔVV outside | Separation | IoU |
|---|---|---|---|---|---|
| Jacobabad | Arid (dry pre-monsoon) | −9.45 dB | −4.18 dB | **−5.27 dB** | 0.370 |
| Emilia-Romagna | Wet (preceding rain) | −1.36 dB | −0.68 dB | **0.68 dB** | 0.057 |
| Wroclaw | Very wet (Aug 2024) | **+1.17 dB** (double-bounce) | +1.57 dB (agriculture) | **−0.40 dB** | 0.029 |

Jacobabad confirms the hypothesis: arid pre-event conditions with correct-direction specular signal produce 6–13× higher IoU than the European cases (0.370 vs 0.057 for Italy peak, vs 0.029 for Wroclaw). The −5.27 dB separation is an order of magnitude stronger than either European case. Wroclaw is a degenerate case — the flood inundated standing September crops, producing flooded-vegetation double-bounce (VV increases), while agricultural harvest adds an even larger change signal across the background.

---

## Project Structure

```
SARFloodAnalysis/
├── README.md
├── emilia_romagna/
│   ├── config/pipeline_config.yaml
│   ├── src/pipeline/          # composite, change, validate, terrain
│   ├── scripts/               # run_processing, run_analysis, make_figures
│   ├── data/                  # external refs, validation JSON, vectors
│   └── outputs/figures/       # fig01–04
├── wroclaw/
│   ├── config/pipeline_config.yaml
│   ├── src/pipeline/          # composite, change, validate
│   ├── scripts/               # run_processing, run_analysis, make_figures
│   ├── data/
│   └── outputs/figures/
└── jacobabad/
    ├── config/pipeline_config.yaml
    ├── src/pipeline/          # composite, change, validate, terrain
    ├── scripts/               # run_processing, run_analysis, make_figures
    ├── data/
    └── outputs/figures/
```

Each case study runs independently from its own directory:

```bash
cd emilia_romagna/          # or wroclaw/ or jacobabad/
python scripts/run_analysis.py
python scripts/make_figures.py
```

CDSE credentials (`CDSE_USER` / `CDSE_PASSWORD`) required for scene download via `scripts/run_processing.py`.

---

## Data Sources

| Dataset | Source |
|---|---|
| Sentinel-1 IW GRD | [Copernicus CDSE](https://dataspace.copernicus.eu/) |
| EMSR flood delineations | [Copernicus EMS](https://emergency.copernicus.eu/) |
| SRTM 1-arc-second DEM | SNAP auxdata (NASA/USGS) |
| JRC Global Surface Water | [EC JRC](https://global-surface-water.appspot.com/) |

---

## References

- Twele, A. et al. (2016). Sentinel-1-based flood mapping: a fully automated processing chain. *Int. J. Remote Sens.* 37(13), 2990–3004.
- Chini, M. et al. (2017). Hierarchical Split-Based Approach for Parametric Thresholding of SAR Images. *IEEE TGRS* 55(12), 6975–6988.
- Pekel, J.F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature* 540, 418–422.
- Farr, T.G. et al. (2007). The Shuttle Radar Topography Mission. *Rev. Geophys.* 45, RG2004.
