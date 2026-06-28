# SAR Flood Mapping — Wroclaw/Lower Silesia, Poland (Storm Boris, September 2024)

A SAR change-detection pipeline for flood extent mapping of the Storm Boris event,
validated against Copernicus Emergency Management Service (EMSR756) delineations.

---

## Event Overview

Storm Boris (12–17 September 2024) brought unprecedented rainfall to Central Europe,
triggering the worst flooding across Poland, the Czech Republic, Austria, and Slovakia
since at least 1997. In Poland, the Lower Silesia (Dolnośląskie) region was most
severely affected, with the Oder (Odra) river and its tributaries — including the
Nysa Kłodzka and Biała Lądecka — flooding towns including Kłodzko, Stronie Śląskie,
Lądek-Zdrój, and many agricultural villages in the Odra floodplain.

The Copernicus Emergency Management Service activated **EMSR756** on 15 September 2024,
producing flood delineations from Sentinel-1 SAR data.

**Key characteristics for SAR flood mapping:**
- Catastrophic multi-day rainfall (200–500 mm in 3 days in some locations)
- Saturated soils from weeks of preceding wet weather (August 2024 was very wet)
- Mixed urban, forested, and agricultural land use
- The September date places crops at full canopy height — SAR cross-polarisation (VH)
  is dominated by volume scattering from crop biomass, masking the flood signal

---

## SAR Scene Selection

| Role | Acquisition | Scene ID | Orbit |
|---|---|---|---|
| **Pre-event** | 3 Sep 2024 05:01 UTC | `S1A_IW_GRDH_1SDV_20240903T050123` | Descending |
| **Post-event** | 15 Sep 2024 05:01 UTC | `S1A_IW_GRDH_1SDV_20240915T050124` | Descending |

The 12-day repeat interval captures the scene 12 days before and on the day of
the flooding peak — an ideal temporal baseline for change detection. However, the
pre-event scene itself was taken during an already-wet period (Storm Boris developed
13–14 September), so soil moisture was elevated even before the main event.

Additional scenes available (used for multi-temporal analysis):
- 22 Aug 2024 — baseline scene in drier conditions
- 27 Sep 2024 — recession image

---

## Pipeline Architecture

```
CDSE download (Sentinel-1 IW GRD)
        │
        ▼
SNAP RTC Processing
  ├── Terrain correction (SRTM 1-sec DEM, UTM Zone 33N, 20m spacing)
  ├── Radiometric calibration → gamma-naught (γ°)
  └── Speckle filtering (Lee 7×7)

        │
        ▼
Change Detection
  ├── Log-ratio: ΔVV = post_VV − pre_VV  (dB)
  ├── ΔVH = post_VH − pre_VH  (dB)
  ├── Combined magnitude: √(ΔVV² + ΔVH²) ≥ threshold
  └── JRC Global Surface Water mask (occurrence ≥ 75%)

        │
        ▼
Threshold Calibration → Validation vs EMSR756
```

---

## Validation Results

### Best Configuration
| Parameter | Value |
|---|---|
| Detection mode | `combined_magnitude` |
| Calibrated threshold | **2.93 dB** |
| JRC permanent water threshold | occurrence ≥ 75% |

### Metrics vs EMSR756 Reference Products

| Reference | IoU | Precision | Recall | F1 | Detected (ha) | Reference (ha) |
|---|---|---|---|---|---|---|
| **Peak flood** (DEL_PRODUCT) | **0.025** | 0.026 | 0.813 | 0.050 | 534,863 | 16,797 |
| **Recession** (DEL_MONIT01) | **0.028** | 0.028 | 0.825 | 0.054 | 534,863 | 19,214 |
| **Maximum extent** (DEL_MONIT01 max) | **0.029** | 0.029 | 0.810 | 0.056 | 534,863 | 20,161 |

### Why IoU is very low — signal physics and multiple confounds

This event represents the most challenging SAR flood scenario, with a root cause
that goes deeper than soil moisture alone:

**The fundamental problem: the flood signal is the wrong sign.**

Open-water flooding on flat terrain produces **specular reflection** — radar energy
bounces away from the sensor, making flooded fields appear *darker* (VV decreases
by 10–20 dB). The Wroclaw flood inundated a densely vegetated, actively cropped
landscape in September. The dominant SAR mechanism here is **double-bounce**: radar
energy reflects off flood water *up into* standing crops and trees, and back to the
sensor — making the flooded area appear *brighter*, not darker.

Measured signal inside the EMSR756 flood reference:
```
Mean ΔVV inside reference:   +1.167 dB  (backscatter INCREASED → double-bounce)
Mean ΔVV outside reference:  +1.571 dB
Signal separation:            0.404 dB  (distributions essentially identical)
```

The change-detection pipeline is designed to flag large magnitude changes (flood =
dark area, large decrease). In Wroclaw the flood is *slightly brighter*, and the
agricultural landscape outside the reference is *even brighter* due to harvest
and tillage from August to September. At every threshold tested, the detected
region is driven by agricultural calendar change, not flood.

Four compounding factors:

1. **Wrong signal mechanism**: Flooded-vegetation double-bounce (positive ΔVV)
   vs the expected specular open-water response (negative ΔVV). The algorithm
   is tuned for the latter, which is not the dominant mechanism here.

2. **September agricultural calendar**: Crops at full canopy (maize, sunflower,
   beet) add large positive VH change from harvest/tillage across the background,
   producing combined magnitude changes *larger* than the flood itself.

3. **Pre-event soil moisture**: The 3 Sep 2024 pre-event scene was already captured
   on saturated soils, compressing the apparent change from pre to post.

4. **Flat IoU curve**: IoU never peaks across any threshold (1–15 dB). This is
   diagnostic: when the distributions are identical at all operating points,
   no threshold can discriminate the classes.

**Potential improvements** (not yet implemented for this case study):
- Multi-temporal pre-event composite from late July/August 2024 to establish a drier baseline
- Integration with optical (Sentinel-2) data for cloud-free dates
- Height-above-nearest-drainage (HAND) raster filtering instead of slope
- Urban/vegetation masking using land cover datasets

---

## Figures

| Figure | Description |
|---|---|
| [`fig01_backscatter_comparison.png`](outputs/figures/fig01_backscatter_comparison.png) | Pre (3 Sep) vs Post (15 Sep) Sentinel-1 VV backscatter with EMSR peak reference |
| [`fig02_change_map.png`](outputs/figures/fig02_change_map.png) | VV log-ratio change map |
| [`fig03_flood_detection.png`](outputs/figures/fig03_flood_detection.png) | TP/FP/FN classification vs peak and maximum extent references |
| [`fig04_validation_metrics.png`](outputs/figures/fig04_validation_metrics.png) | Threshold calibration sweep and metrics bar chart |

---

## Data Sources

| Dataset | Source | Purpose |
|---|---|---|
| Sentinel-1 IW GRD | [CDSE](https://dataspace.copernicus.eu/) | SAR scenes |
| EMSR756 reference delineations | [Copernicus EMS](https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR756) | Ground-truth validation |
| SRTM 1-arc-second DEM | SNAP auxdata | Terrain correction |
| JRC Global Surface Water | [EC JRC](https://global-surface-water.appspot.com/) | Permanent water mask |

---

## Reproducing Results

```bash
cd wroclaw/
pip install -e .

# 1. Download and process Sentinel-1 scenes (requires SNAP + CDSE credentials)
python -m scripts.run_processing

# 2. Run change detection and validation
python -m scripts.run_analysis

# 3. Generate figures
python -m scripts.make_figures
```

Full RTC data (~15 GB) and analysis rasters are stored in the original
`SARFloodWroclaw/` project directory.

---

## Notes

This is the lowest-IoU case study in the collection and intentionally included
to demonstrate the **failure modes** of SAR change detection. It shows that:

- Recall can be very high even when IoU is very low (detector is "finding" flood but
  also flagging everything else)
- Autumn floods in temperate agricultural regions are among the hardest SAR targets
- Storm Boris is a well-studied event; the same limitations are documented in EMS
  and academic literature for September/October European floods

See the [master README](../README.md) for the full cross-case-study comparison.
