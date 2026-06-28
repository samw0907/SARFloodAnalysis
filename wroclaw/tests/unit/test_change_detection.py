import numpy as np
import pytest
from src.pipeline.change import (
    compute_log_ratio,
    apply_flood_mask,
    remove_small_patches,
)


def test_compute_log_ratio_is_post_minus_pre():
    pre = np.array([[-10.0, -8.0], [-12.0, -6.0]], dtype=np.float32)
    post = np.array([[-15.0, -8.0], [-10.0, -9.0]], dtype=np.float32)
    result = compute_log_ratio(pre, post)
    expected = np.array([[-5.0, 0.0], [2.0, -3.0]], dtype=np.float32)
    np.testing.assert_array_almost_equal(result, expected)


def test_compute_log_ratio_zero_change():
    arr = np.array([[-10.0, -5.0]], dtype=np.float32)
    result = compute_log_ratio(arr, arr)
    np.testing.assert_array_equal(result, np.zeros_like(arr))


def test_apply_flood_mask_large_change_flagged():
    # Storm Boris: combined magnitude captures both decreases (open water)
    # and increases (flooded-vegetation double-bounce)
    change_vv = np.array([[-10.0, -0.5]], dtype=np.float32)
    change_vh = np.array([[-8.0, 0.2]], dtype=np.float32)
    result = apply_flood_mask(change_vv, change_vh, threshold_db=5.0)
    # pixel 0: sqrt(100 + 64) ≈ 12.8 → flooded
    # pixel 1: sqrt(0.25 + 0.04) ≈ 0.54 → not flooded
    assert result[0, 0] == 1
    assert result[0, 1] == 0


def test_apply_flood_mask_positive_change_also_flagged():
    # Unlike directional-decrease pipelines, Wroclaw flags large increases too
    change_vv = np.array([[8.0]], dtype=np.float32)
    change_vh = np.array([[6.0]], dtype=np.float32)
    result = apply_flood_mask(change_vv, change_vh, threshold_db=5.0)
    # sqrt(64 + 36) = 10 → flooded
    assert result[0, 0] == 1


def test_apply_flood_mask_below_threshold_not_flagged():
    change_vv = np.array([[0.5, 0.3]], dtype=np.float32)
    change_vh = np.array([[0.4, 0.2]], dtype=np.float32)
    result = apply_flood_mask(change_vv, change_vh, threshold_db=5.0)
    np.testing.assert_array_equal(result, np.zeros((1, 2), dtype=np.uint8))


def test_apply_flood_mask_permanent_water_suppressed():
    change_vv = np.array([[-10.0, -10.0]], dtype=np.float32)
    change_vh = np.array([[-8.0, -8.0]], dtype=np.float32)
    perm_water = np.array([[1, 0]], dtype=np.uint8)
    result = apply_flood_mask(change_vv, change_vh, threshold_db=5.0,
                              permanent_water_mask=perm_water)
    assert result[0, 0] == 0  # masked by permanent water
    assert result[0, 1] == 1


def test_apply_flood_mask_nan_safe():
    change_vv = np.array([[float("nan"), -10.0]], dtype=np.float32)
    change_vh = np.array([[float("nan"), -8.0]], dtype=np.float32)
    result = apply_flood_mask(change_vv, change_vh, threshold_db=5.0)
    assert result[0, 0] == 0  # NaN → not flooded, no exception


def test_remove_small_patches_removes_isolated_pixel():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[10, 10] = 1
    result = remove_small_patches(mask, min_pixels=5)
    assert result[10, 10] == 0


def test_remove_small_patches_keeps_large_patch():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:15, 5:15] = 1  # 10×10 = 100-pixel patch
    result = remove_small_patches(mask, min_pixels=5)
    assert result[10, 10] == 1
