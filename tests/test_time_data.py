from datetime import datetime

import pytest

from synodic.time_data import TimeData, calendar_string, time_fields


def test_utc_validity_and_separate_projections(time_data):
    td, ts = time_data, time_data.ts
    historical = time_fields(ts.tt(1926, 9, 29), td)
    assert historical["utc"] is None and historical["utc_provisional"] is None
    assert historical["utc_status"] == "unavailable_before_1972"
    present = time_fields(ts.utc(2024, 4, 8, 18, 20, 51.5), td)
    assert present["utc"] == "2024-04-08T18:20:51.500Z"
    assert present["local_fixed_offset"] == "2024-04-09T02:20:51.500+08:00"
    assert present["utc_provisional"] is None
    future = time_fields(ts.tt(2126, 1, 1), td)
    assert future["utc"] is None and future["local_fixed_offset"] is None
    assert future["utc_provisional"] is not None
    assert future["utc_status"] == "provisional_constant_tai_minus_utc"
    assert td.utc_status(ts.from_datetime(td.expires)) == "provisional_constant_tai_minus_utc"
    assert td.utc_status(ts.from_datetime(td.expires) - 1 / 86400) == "within_leap_table_validity"


def test_calendar_rollover_and_split_jd(time_data):
    ts = time_data.ts
    assert calendar_string(ts.tt(2024, 12, 31, 23, 59, 59.9997), "tt") == "2025-01-01T00:00:00.000"
    t = ts.tt_jd(2460000, 300.123456789)
    f = time_fields(t, time_data)
    datetime.fromisoformat(f["tt"])
    datetime.fromisoformat(f["ut1_estimate"])
    assert 0 <= f["tt_jd_fraction"] < 1
    assert 0 <= f["tdb_jd_fraction"] < 1
    restored = ts.tt_jd(f["tt_jd_whole"], f["tt_jd_fraction"])
    assert abs(float(restored - t)) < 1e-12


def test_leap_second_not_lost(time_data):
    ts = time_data.ts
    f = time_fields(ts.utc(2016, 12, 31, 23, 59, 60.25), time_data)
    assert f["utc"] == "2016-12-31T23:59:60.250Z"
    assert float(ts.utc(2017, 1, 1) - ts.utc(2016, 12, 31, 23, 59, 59)) * 86400 == pytest.approx(2)


def test_invalid_leap_file(tmp_path):
    path = tmp_path / "bad.list"
    path.write_text("2272060800 10\n")
    with pytest.raises(ValueError, match="expiry"):
        TimeData.read(path)
