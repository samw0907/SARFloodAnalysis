import numpy as np
import pytest
from src.pipeline.validate import compute_metrics


def test_compute_metrics_perfect_prediction():
    pred = np.array([[1, 1, 0], [0, 1, 0]], dtype=np.uint8)
    ref = pred.copy()
    m = compute_metrics(pred, ref)
    assert m["iou"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0


def test_compute_metrics_no_overlap():
    pred = np.array([[1, 0], [0, 0]], dtype=np.uint8)
    ref = np.array([[0, 1], [0, 0]], dtype=np.uint8)
    m = compute_metrics(pred, ref)
    assert m["iou"] == 0.0
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0


def test_compute_metrics_known_values():
    # TP=1 (top-left), FP=1 (top-right), FN=1 (bottom-left)
    pred = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    ref = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    m = compute_metrics(pred, ref)
    assert m["iou"] == pytest.approx(1 / 3, abs=0.001)
    assert m["precision"] == pytest.approx(0.5, abs=0.001)
    assert m["recall"] == pytest.approx(0.5, abs=0.001)
    assert m["f1"] == pytest.approx(0.5, abs=0.001)
    assert m["tp"] == 1
    assert m["fp"] == 1
    assert m["fn"] == 1


def test_compute_metrics_empty_prediction():
    pred = np.zeros((10, 10), dtype=np.uint8)
    ref = np.ones((10, 10), dtype=np.uint8)
    m = compute_metrics(pred, ref)
    assert m["iou"] == 0.0
    assert m["recall"] == 0.0
    assert m["precision"] == 0.0


def test_compute_metrics_empty_reference():
    pred = np.ones((10, 10), dtype=np.uint8)
    ref = np.zeros((10, 10), dtype=np.uint8)
    m = compute_metrics(pred, ref)
    assert m["iou"] == 0.0
    assert m["precision"] == 0.0


def test_compute_metrics_area_ha():
    # 20m pixels → 400m² = 0.04 ha each
    pred = np.zeros((5, 5), dtype=np.uint8)
    ref = np.zeros((5, 5), dtype=np.uint8)
    pred[0, :] = 1  # 5 FP
    pred[1, :] = 1  # 5 TP
    ref[1, :] = 1   # 5 TP
    ref[2, :] = 1   # 5 FN
    m = compute_metrics(pred, ref)
    # detected = TP + FP = 10 pixels × 0.04 ha = 0.4 ha
    assert m["detected_area_ha"] == pytest.approx(0.4, abs=0.001)
    # reference = TP + FN = 10 pixels × 0.04 ha = 0.4 ha
    assert m["reference_area_ha"] == pytest.approx(0.4, abs=0.001)
