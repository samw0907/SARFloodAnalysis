import os
import tempfile
import pytest
from src.pipeline.composite import find_rtc_file


def test_find_rtc_file_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        fname = "S1A__IW___D_20230510T051945_VV_gamma0-rtc_db.tif"
        open(os.path.join(tmpdir, fname), "w").close()
        result = find_rtc_file(tmpdir, "2023-05-10", "VV")
        assert result == os.path.join(tmpdir, fname)


def test_find_rtc_file_hyphenated_and_compact_dates_equivalent():
    with tempfile.TemporaryDirectory() as tmpdir:
        fname = "S1A__IW___D_20230510T051945_VH_gamma0-rtc_db.tif"
        open(os.path.join(tmpdir, fname), "w").close()
        # both "2023-05-10" and "20230510" should resolve the same file
        r1 = find_rtc_file(tmpdir, "2023-05-10", "VH")
        r2 = find_rtc_file(tmpdir, "20230510", "VH")
        assert os.path.basename(r1) == os.path.basename(r2) == fname


def test_find_rtc_file_not_found_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError, match="No RTC file found"):
            find_rtc_file(tmpdir, "2023-05-10", "VV")


def test_find_rtc_file_wrong_polarisation_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Only VH exists; looking for VV → FileNotFoundError
        fname = "S1A__IW___D_20230510T051945_VH_gamma0-rtc_db.tif"
        open(os.path.join(tmpdir, fname), "w").close()
        with pytest.raises(FileNotFoundError):
            find_rtc_file(tmpdir, "2023-05-10", "VV")


def test_find_rtc_file_ignores_non_gamma0_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # A file with the right date and polarisation but NOT gamma0-rtc should be ignored
        fname = "S1A__IW___D_20230510T051945_VV_localIncidenceAngle.tif"
        open(os.path.join(tmpdir, fname), "w").close()
        with pytest.raises(FileNotFoundError):
            find_rtc_file(tmpdir, "2023-05-10", "VV")
