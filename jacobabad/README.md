# SAR Flood Mapping — Jacobabad District, Pakistan (2022 Mega-Flood)

> **Status: In Progress** — EMSR629 reference data acquired. Sentinel-1 scene
> selection and download pending. JRC water tile download required before first run.

---

## Event Overview

The 2022 Pakistan floods were described by the UN as a "climate catastrophe of epic
proportions", affecting more than one-third of the country. Monsoon rains from June
through September 2022 were 190% above average nationally; in Sindh and Balochistan
provinces, rainfall exceeded 500% of normal. Over 1,700 people died, 33 million were
displaced, and approximately 2 million hectares of cropland were inundated.

**Jacobabad district, Sindh** (centred ~68.4°E, 27.5°N) is a particularly compelling
study area for SAR flood mapping because:

- **Arid climate**: Normal annual rainfall <150 mm; pre-flood soils are bone-dry
- **Flat Indus plain**: Elevation 50–80 m above sea level; slopes < 0.5°
- **Agriculturally homogeneous**: Bare soil or sparse low vegetation in pre-monsoon season
- **Expected strong SAR signal**: VV backscatter drops 15–25 dB from dry bare soil
  to open flood water — an extreme contrast vs the Italy/Wroclaw events

This case study is expected to demonstrate SAR flood mapping **at its best**, in
contrast to the difficult wet-soil confound cases.

---

## Study Area

| Parameter | Value |
|---|---|
| Location | Jacobabad District, Sindh Province, Pakistan |
| Coordinates | 68.07–68.44°E, 27.46–27.70°N (EMSR629 reference extent) |
| Processing bbox | [67.8, 27.2, 68.7, 28.0] |
| UTM Zone | 42N (EPSG:32642) |
| Area | ~50,184 ha reference flood extent (EMSR629) |

---

## Reference Data

The Copernicus Emergency Management Service activated **EMSR629** for the Pakistan
2022 floods. The available reference product is:

| File | Polygons | Area (ha) | Coverage |
|---|---|---|---|
| `EMSR629_AOI01_DEL_PRODUCT_observedEventA_r1_v2.shp` | 9,690 | 50,184 | Peak flood extent, Jacobabad AOI01 |

---

## Expected Methodology

Given the arid-climate context, the full Italy pipeline applies with modifications:

```yaml
change_detection:
  mode: directional_decrease    # open-water specular → strong VV decrease
  threshold_db: 3.0             # will be auto-calibrated

terrain:
  slope_threshold_deg: 2.0      # Indus plain is essentially flat
```

The `directional_decrease` mode (`sqrt(min(ΔVV,0)² + min(ΔVH,0)²)`) is expected
to outperform `combined_magnitude` here because:
1. Pre-event soil is dry → no soil moisture confound → VV decrease is diagnostic
2. Minimal crop canopy → VH also decreases cleanly for open water
3. No wet-soil background signal to confuse the threshold

---

## Pre-Run Checklist

Before running the pipeline, the following steps are required:

- [ ] **Scene selection**: Confirm exact pre/post scene IDs via Copernicus Browser
      - Pre: July 2022 (dry season baseline)
      - Post: Late August / September 2022 (peak inundation)
      - Use descending orbit for consistency with other case studies
- [ ] **Scene download**: `python -m scripts.run_processing` (requires CDSE credentials)
- [ ] **JRC water tile**: Download tile `60E_20N` (covers 20–30°N, 60–70°E)
      via `python -m scripts.download_jrc` or manual download from JRC portal
      → save as `data/external/jrc_water_pakistan.tif`
- [ ] **SNAP auxdata**: SRTM tiles N27E067–N28E068 will auto-cache during RTC
- [ ] **Verify config dates**: Update `config/pipeline_config.yaml` pre/post dates
      after confirming scene coverage via Copernicus Browser

---

## Expected Results

Based on the event characteristics and published SAR flood mapping benchmarks:

| Metric | Expected range |
|---|---|
| IoU vs EMSR reference | **0.40–0.70** |
| Precision | 0.50–0.85 |
| Recall | 0.50–0.80 |

These represent the "best-case" end of the performance spectrum — a stark contrast
to Wroclaw (IoU 0.029) and Emilia-Romagna (IoU 0.054).

---

## Data Sources

| Dataset | Source | Purpose |
|---|---|---|
| Sentinel-1 IW GRD | [CDSE](https://dataspace.copernicus.eu/) | SAR scenes (to download) |
| EMSR629 reference | [Copernicus EMS](https://emergency.copernicus.eu/mapping/list-of-activations-rapid/EMSR629) | Ground-truth ✓ acquired |
| SRTM DEM | SNAP auto-cache | Terrain correction + slope filter |
| JRC Global Surface Water tile 60E_20N | [EC JRC](https://global-surface-water.appspot.com/) | Permanent water mask (to download) |

---

## Reproducing Results (once data is acquired)

```bash
cd jacobabad/
pip install -e .

# Download and RTC-process Sentinel-1 scenes
python -m scripts.run_processing

# Generate terrain slope mask (from SNAP SRTM cache)
python -m scripts.prepare_terrain

# Change detection, calibration, validation
python -m scripts.run_analysis

# Generate figures
python -m scripts.make_figures
```

See the [master README](../README.md) for the full methodology overview and
cross-case-study comparison.
