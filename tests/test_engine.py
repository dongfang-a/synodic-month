import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from skyfield.almanac import moon_phase

from synodic.engine import DAY_S, find_events, pair_lunations, signed_residual
from synodic.time_data import calendar_string

FIXTURES = Path(__file__).parent / "fixtures"
USNO_PHASE = {"New Moon": 0, "First Quarter": 1, "Full Moon": 2, "Last Quarter": 3}


@pytest.mark.parametrize("year,max_seconds", [(1926,60), (1980,60), (2000,60), (2024,60), (2100,120)])
def test_usno_reference_year(eph, time_data, year, max_seconds):
    """Independent minute-resolution almanac check, NOT millisecond validation.

    A one-minute envelope is deliberate: the USNO 2024 snapshot differs by
    up to 39.705 seconds, beyond rounding alone. Its cause is not established;
    tighter astronomical-model validation uses independent Horizons positions.
    Historical/future UT is compared to model-dependent UT1; allow differing
    future Delta T predictions rather than interpreting future UT as known UTC.
    """
    ts = time_data.ts
    scale = "utc" if 1972 <= year <= 2024 else "ut1"
    boundary = getattr(ts, scale)
    events = find_events(eph, ts, boundary(year, 1, 1), boundary(year + 1, 1, 1))
    refs = json.loads((FIXTURES / f"usno-{year}.json").read_text())["phasedata"]
    assert len(events) == len(refs)
    differences = []
    for actual, expected in zip(events, refs):
        assert actual.phase == USNO_PHASE[expected["phase"]]
        stamp = f'{expected["year"]:04d}-{expected["month"]:02d}-{expected["day"]:02d}T{expected["time"]}:00'
        expected_dt = datetime.fromisoformat(stamp)
        actual_stamp = actual.time.utc_iso(places=3).removesuffix("Z") if scale == "utc" else calendar_string(actual.time, "ut1")
        difference = (datetime.fromisoformat(actual_stamp) - expected_dt).total_seconds()
        differences.append(abs(difference))
    assert max(differences) < max_seconds


def test_independent_horizons_longitudes(eph, time_data):
    """Independent DE441 / IAU76-80 check at 24 epochs across 1926--2126."""
    from decimal import Decimal

    samples = json.loads((FIXTURES / "horizons-samples.json").read_text())["samples"]
    ts = time_data.ts
    for sample in samples:
        jd = Decimal(sample["tt_jd"])
        whole = int(jd)
        t = ts.tt_jd(whole, float(jd - whole))
        angle = moon_phase(eph, t).degrees
        reference = (sample["moon_longitude_degrees"] - sample["sun_longitude_degrees"]) % 360
        assert abs(signed_residual(angle, reference)) * 3600 < .02
        # Independently verify these are phase roots, not merely matching
        # arbitrary positions from two libraries.
        assert abs(signed_residual(reference, sample["phase"] * 90)) * 3600 < .02
        events = find_events(eph, ts, t - .1, t + .1)
        assert len(events) == 1 and events[0].phase == sample["phase"]
        assert abs(float(events[0].time - t)) * DAY_S < .001


def test_root_brackets_and_longitude_wrap(eph, time_data):
    ts = time_data.ts
    events = find_events(eph, ts, ts.tt(2024, 1, 1), ts.tt(2025, 1, 1))
    assert len(events) == 50
    for event in events:
        target = event.phase * 90
        # Both sides must straddle the continuous physical root, including 0°.
        before = signed_residual(moon_phase(eph, event.time - .002 / DAY_S).degrees, target)
        after = signed_residual(moon_phase(eph, event.time + .002 / DAY_S).degrees, target)
        assert before < 0 < after
        assert event.bracket_seconds <= .001
        assert abs(event.residual_arcseconds) < .0004


def test_chunk_overlap_and_solver_convergence(eph, time_data):
    ts = time_data.ts
    a, b = ts.tt(2024, 1, 1), ts.tt(2024, 6, 1)
    reference = find_events(eph, ts, a, b, tolerance_seconds=.0001)
    # Place a chunk edge within one millisecond of an actual event.
    chunk = float(reference[1].time - a)
    other = find_events(eph, ts, a, b, chunk_days=chunk, step_days=.75)
    assert [e.phase for e in reference] == [e.phase for e in other]
    assert max(abs(float(x.time - y.time)) * DAY_S for x, y in zip(reference, other)) < .001


def test_empty_interval_and_subinterval_selection(eph, time_data):
    ts = time_data.ts
    assert find_events(eph, ts, ts.tt(2024, 1, 1), ts.tt(2024, 1, 2)) == []
    events = find_events(eph, ts, ts.tt(2024, 4, 1), ts.tt(2024, 5, 1))
    new = next(e for e in events if e.phase == 0)
    assert len(find_events(eph, ts, new.time - .01 / DAY_S, new.time + .01 / DAY_S)) == 1
    assert not find_events(eph, ts, new.time + .01 / DAY_S, new.time + .02 / DAY_S)


def test_lunation_padding(eph, time_data):
    ts = time_data.ts
    a, b = ts.tt(2024, 1, 1), ts.tt(2025, 1, 1)
    padded = find_events(eph, ts, a - 32, b + 32)
    pairs = pair_lunations(padded, a, b)
    assert len(pairs) == 13
    assert pairs[-1][2].time > b
    for new, full, nxt in pairs:
        assert new.time < full.time < nxt.time
        assert 29.2 < float(nxt.time - new.time) < 29.9
    with pytest.raises(RuntimeError, match="padding"):
        pair_lunations([e for e in padded if e.time < b], a, b)


def test_reject_bad_inputs_and_coverage(eph, time_data):
    ts = time_data.ts
    with pytest.raises(ValueError, match="coverage"):
        find_events(eph, ts, ts.tt(1800, 1, 1), ts.tt(1801, 1, 1))
    with pytest.raises(ValueError, match="precede"):
        find_events(eph, ts, ts.tt(2025), ts.tt(2024))
    for bad in [0, 1e-9, np.nan, np.inf]:
        with pytest.raises(ValueError, match="Tolerance"):
            find_events(eph, ts, ts.tt(2024), ts.tt(2025), tolerance_seconds=bad)
