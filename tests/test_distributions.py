import json
from pathlib import Path

import pytest

from synodic.distributions import analyse, derive_sample


def record(new, full, minutes):
    return {"new_utc": new, "full_utc": full,
            "new_utc_status": "within_leap_table_validity", "full_utc_status": "within_leap_table_validity",
            "new_tt": "fixture", "full_tt": "fixture", "new_to_full_tt_days": minutes / 1440,
            "full_inside_requested_interval": True}


def test_lunar_day_uses_local_midnights_not_elapsed_days():
    # Both have exactly 14d + 2h elapsed, but different lunar days.
    a = derive_sample(record("2024-01-01T14:00:00Z", "2024-01-15T16:00:00Z", 14 * 1440 + 120), 1)
    b = derive_sample(record("2024-01-01T16:00:00Z", "2024-01-15T18:00:00Z", 14 * 1440 + 120), 2)
    assert a["lunar_day"] == 16 and b["lunar_day"] == 15
    assert a["full_clock_hour"] == 0 and b["full_clock_hour"] == 2


def test_exact_minute_hour_bin_edges():
    a = derive_sample(record("2024-01-01T16:00:00Z", "2024-01-15T16:59:59.999Z", 20000), 1)
    b = derive_sample(record("2024-01-01T16:00:00Z", "2024-01-15T17:00:00Z", 20001 - 1e-6), 2)
    assert a["interval_bin_start_minute"] == b["interval_bin_start_minute"] == 20000
    assert a["hour_bin_start_from_day14"] == 24
    assert b["hour_bin_start_from_day14"] == 25


def test_outside_requested_lunar_days_is_not_silently_discarded():
    with pytest.raises(ValueError, match="outside"):
        derive_sample(record("2024-01-01T16:00:00Z", "2024-01-18T16:00:00Z", 17 * 1440), 1)


def test_actual_sample_conservation_and_trim():
    path = Path(__file__).resolve().parents[1] / "output/1926-2126/results.json"
    if not path.exists():
        pytest.skip("Generate the 200-year data before running the distribution integration test.")
    source = json.loads(path.read_text(encoding="utf-8"))
    result = analyse(source)
    assert len(result["samples"]) == 2473
    for key in ("minute_bins", "hour_bins", "day_bins"):
        assert sum(row["count"] for row in result[key]) == 2473
        assert sum(row["probability"] for row in result[key]) == pytest.approx(1)
    assert len(result["hour_bins"]) == 96
    shown = [r for r in result["hour_bins"] if r["shown_in_chart"]]
    assert shown[0]["count"] > 0 and shown[-1]["count"] > 0
    assert len(shown) == shown[-1]["right_hour_exclusive"] - shown[0]["left_hour_from_day14"]
    assert all(row["count"] == 0 for row in result["hour_bins"] if not row["shown_in_chart"])
    assert all(s["full_tt"] < "2126-09-29" for s in result["samples"])
