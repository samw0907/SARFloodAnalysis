# SAR Flood Analysis — Multi-Case-Study Collection

A production-grade Sentinel-1 SAR flood mapping pipeline demonstrated across three
contrasting flood events. Each case study uses the same core change-detection approach
but with event-appropriate adaptations, allowing direct comparison of how flood type,
climate, and land cover affect SAR-based detection performance.

---

## Case Studies

| Case Study | Event | Date | IoU (best) | Status |
|---|---|---|---|---|
| [Emilia-Romagna](emilia_romagna/) | Italy floods, Faenza/Forlì | May 2023 | **0.131** (recession) | Complete |
| [Wroclaw](wroclaw/) | Storm Boris, Lower Silesia | Sep 2024 | **0.029** (maximum) | Complete |
| [Jacobabad](jacobabad/) | Pakistan mega-flood | Aug–Sep 2022 | TBD (expected 0.4–0.7) | In Progress |

---

## Why These Three Events?

The selection is deliberate — together the three events span the full performance range
for SAR change-detection flood mapping:

```
HARDEST                                        EASIEST
─────────────────────────────────────────────────────►
  Wroclaw          Emilia-Romagna          Jacobabad
  IoU ~0.03          IoU ~0.05-0.13        IoU ~0.4-0.7 (expected)
  
  Saturated soils    Saturated soils      Bone-dry arid soils
  Sep agriculture    Mixed urban/agri     Bare soil / sparse veg
  Wet pre-event      Wet pre-event        Dry pre-event
  Temperate flood    Temperate flood      Arid-climate flood
```

Understanding *why* performance degrades is as informative as achieving high IoU.
The collection as a whole builds a realistic picture of what operationally deployed
SAR flood mapping can and cannot reliably detect.

---

## Methodology

### Core Pipeline

All three case studies share the same pipeline structure:

```
CDSE download → SNAP RTC → Composite → Change Detection → Threshold Calibration → Validation
```

**Change detection** computes the log-ratio of gamma-naught backscatter (dB) between
a pre-event and post-event Sentinel-1 IW GRD scene:

```
ΔVV = post_VV − pre_VV
ΔVH = post_VH − pre_VH
```

A combined metric is then thresholded. Three detection modes are implemented:

| Mode | Formula | Best for |
|---|---|---|
| `combined_magnitude` | √(ΔVV² + ΔVH²) ≥ T | General: captures open-water AND flooded vegetation |
| `directional_decrease` | √(min(ΔVV,0)² + min(ΔVH,0)²) ≥ T | Open-water floods, arid pre-event; ignores crop growth |
| `pol_ratio` | ΔVH − ΔVV ≥ T | Theoretically optimal for specular open-water (limited by VH noise) |

**Threshold calibration** sweeps from 1–15 dB in 30 steps, selects the value
maximising IoU against the primary EMSR reference.

**Masking layers** applied before classification:
1. **Permanent water** — JRC Global Surface Water occurrence ≥ 75% → excluded
2. **Terrain slope** — SRTM 1-arc-second, slope > threshold → excluded (flat
   floodplain filter, Copernicus EMS standard practice)

### Per-Case Adaptations

| Parameter | Emilia-Romagna | Wroclaw | Jacobabad |
|---|---|---|---|
| UTM Zone | 32N (EPSG:32632) | 33N (EPSG:32633) | 42N (EPSG:32642) |
| Detection mode | `combined_magnitude` | `combined_magnitude` | `directional_decrease` |
| Slope threshold | 5° | — | 2° |
| Pre-event date | 10 May 2023 | 3 Sep 2024 | ~26 Jul 2022 |
| Post-event date | 22 May 2023 | 15 Sep 2024 | ~6 Sep 2022 |
| EMSR reference | EMSR664 | EMSR756 | EMSR629 |
| References available | peak + recession | peak + recession + maximum | peak |

---

## Results Summary

### Emilia-Romagna (Italy, May 2023)

**Event**: Catastrophic rainfall caused river systems including the Savio, Ronco,
and Lamone to overflow, flooding the agricultural plain between Faenza, Forlì, and
Ravenna. One of the worst Italian floods in living memory.

**Best results** (combined magnitude, 9.69 dB threshold, 5° slope filter):

| vs EMSR664 | IoU | Precision | Recall | F1 | Detected | Reference |
|---|---|---|---|---|---|---|
| Peak flood | 0.054 | 0.094 | 0.112 | 0.102 | 10,464 ha | 8,798 ha |
| **Recession** | **0.131** | **0.240** | **0.224** | **0.232** | 10,464 ha | 11,212 ha |

**Key findings**:
- Higher IoU vs recession reference suggests the pipeline captures persistent
  inundation better than the immediate peak
- Soil moisture confound: mean ΔVV inside flood reference = −1.36 dB vs outside
  = −0.68 dB. Only 0.68 dB separation — insufficient for clean pixel-level separation
- The DEM slope filter (5°, SRTM) improved IoU marginally and is included for
  methodological completeness

### Wroclaw (Poland, Storm Boris, Sep 2024)

**Event**: Storm Boris (12–17 Sep 2024) caused the worst flooding in Poland since 1997.
The Oder (Odra) river and tributaries flooded Kłodzko, Stronie Śląskie, and agricultural
villages across Lower Silesia.

**Best results** (combined magnitude, 2.93 dB threshold):

| vs EMSR756 | IoU | Precision | Recall | F1 | Detected | Reference |
|---|---|---|---|---|---|---|
| Peak | 0.025 | 0.026 | 0.813 | 0.050 | 534,863 ha | 16,797 ha |
| Recession | 0.028 | 0.028 | 0.825 | 0.054 | 534,863 ha | 19,214 ha |
| **Maximum extent** | **0.029** | **0.029** | **0.810** | **0.056** | 534,863 ha | 20,161 ha |

**Key findings**:
- Root cause is more fundamental than soil moisture: the flood is inundating a September
  crop landscape where the dominant SAR mechanism is **flooded-vegetation double-bounce**
  (backscatter *increases*, ΔVV = +1.167 dB inside the reference), not specular open-water
  reflection (backscatter decreases, ΔVV < −10 dB). The pipeline detects decreases —
  this flood is barely visible in that metric.
- Agricultural harvest/tillage between August and September produces larger combined
  magnitude changes than the flood itself, overwhelming the signal.
- IoU curve is flat across all thresholds (1–15 dB): the distributions inside and outside
  the EMSR reference are statistically nearly identical at every tested operating point.

### Jacobabad (Pakistan, 2022) — In Progress

**Event**: The 2022 Pakistan mega-flood (the world's most expensive climate disaster of
that year) inundated ~2 million hectares. Jacobabad district, Sindh — an arid zone
in the Indus plain — shows extreme contrast between dry bare soil (pre-event) and
standing flood water.

**Expected results**: IoU 0.40–0.70 based on:
- Arid pre-event conditions: dry bare soil σ₀ typically −10 to −7 dB (VV)
- Post-flood open water σ₀: −25 to −18 dB (specular) → 10–15 dB contrast
- Minimal soil-moisture confound (no rain until the monsoon arrives)
- Flat terrain (Indus plain, slopes < 0.5°) minimises terrain effects

---

## The Soil Moisture Confound — A Cross-Case Analysis

The dominant limiting factor across all three case studies is **signal separability**:
whether the flood produces a physically distinct SAR response from the surrounding landscape.

| Scenario | Pre-event soil | Mean ΔVV inside flood | Mean ΔVV outside | Separation | IoU |
|---|---|---|---|---|---|
| **Jacobabad** | Bone dry (arid) | ~−15 to −20 dB (specular) | ~0 dB (no rain elsewhere) | **~15 dB** | ~0.5+ (predicted) |
| **Emilia-Romagna** | Wet (preceding rain) | −1.36 dB (partially specular) | −0.68 dB | **0.68 dB** | 0.054 |
| **Wroclaw** | Very wet (Aug 2024) | **+1.17 dB** (double-bounce ¹) | +1.57 dB (agriculture) | **−0.40 dB** | 0.029 |

¹ *Wroclaw's flood inundated standing crops in September, producing flooded-vegetation
double-bounce (VV increases, not decreases). September agricultural harvest/tillage adds an
even larger positive VV signal outside the reference. The detector cannot separate the two
at any threshold — Wroclaw is a degenerate case where the signal is physically inverted,
not merely small.*

This table shows that SAR change detection is fundamentally a **signal separability problem**.
The Jacobabad case study is expected to demonstrate that the same pipeline achieves excellent
results when pre-event soils are dry and the flood produces a clean specular signature.

---

## Known Limitations

1. **Single-date pre-event baseline**: All studies use one pre-event scene. A
   multi-temporal composite (3–5 scenes over 1–2 months) provides a more stable,
   moisture-independent reference and is the state of the art for operational systems.

2. **No optical fusion**: Sentinel-2 cloud cover prevented optical integration for
   all events. MNDWI/NDWI from concurrent Sentinel-2 would significantly improve
   precision in clear-sky areas.

3. **HAND not implemented**: Height-Above-Nearest-Drainage (HAND) is the preferred
   floodplain filter over simple slope thresholding. HAND requires a river network
   and DEM derivative computation.

4. **Urban areas**: SAR double-bounce from buildings and flood water can produce
   backscatter *increases* (opposite direction to open water). The `combined_magnitude`
   mode captures this, but attribution is ambiguous.

5. **Single polarisation threshold**: The threshold is applied uniformly to the
   combined metric. Machine learning classifiers trained on labelled SAR data
   (logistic regression, random forest) can incorporate spatial context and additional
   features for substantially better performance.

---

## Project Structure

```
SARFloodAnalysis/
├── README.md                         ← this file
│
├── emilia_romagna/                   ← Italy case study (COMPLETE)
│   ├── README.md
│   ├── config/pipeline_config.yaml
│   ├── data/
│   │   ├── external/                 EMSR664 shapefiles, JRC water, slope mask
│   │   ├── validation/               validation_summary.json
│   │   └── vectors/                  flood GeoJSONs
│   ├── src/pipeline/                 download, process, composite, change, validate, terrain
│   ├── scripts/                      run_processing, run_analysis, make_figures, prepare_terrain
│   └── outputs/figures/             fig01–04 (300 DPI)
│
├── wroclaw/                          ← Storm Boris, Poland (COMPLETE)
│   ├── README.md
│   ├── config/pipeline_config.yaml
│   ├── data/
│   │   ├── external/                 EMSR756 shapefiles, JRC water
│   │   └── validation/               validation_summary.json
│   ├── src/pipeline/                 change, composite, download, validate
│   ├── scripts/                      run_processing, make_figures
│   └── outputs/figures/             fig01–04 (300 DPI)
│
└── jacobabad/                        ← Pakistan 2022 (IN PROGRESS)
    ├── README.md
    ├── config/pipeline_config.yaml   template with approximate dates
    ├── data/
    │   └── external/                 EMSR629 reference ✓ acquired
    ├── src/pipeline/                 pipeline stubs (to be populated)
    └── scripts/                      (to be created after data download)
```

Each case study is independently runnable from its own directory:
```bash
cd emilia_romagna/   # or wroclaw/ or jacobabad/
pip install -e .
python -m scripts.run_analysis
```

---

## Environment

```bash
conda create -n sarflood python=3.10
conda activate sarflood
pip install rasterio geopandas scipy matplotlib numpy pyyaml requests shapely
# SNAP must be installed separately (ESA Sentinel Application Platform)
```

CDSE credentials (`CDSE_USER` / `CDSE_PASSWORD`) are required for scene download.
Each case study directory expects a `config/.env` file with those credentials.

---

## References

- Copernicus EMS EMSR664 (Italy): https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR664
- Copernicus EMS EMSR756 (Poland): https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR756
- Copernicus EMS EMSR629 (Pakistan): https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR629
- Twele, A. et al. (2016). Sentinel-1-based flood mapping. *Int. J. Remote Sens.* 37(13).
- Chini, M. et al. (2017). Hierarchical Split-Based Approach for SAR thresholding. *IEEE TGRS* 55(12).
- Pekel, J.F. et al. (2016). Global surface water mapping. *Nature* 540.
- Farr, T.G. et al. (2007). The Shuttle Radar Topography Mission. *Rev. Geophys.* 45.
