"""Offline validation report: saved 200-year output + independent references."""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
from skyfield.almanac import moon_phase
from skyfield.api import load_file

from synodic.cli import sha256
from synodic.engine import DAY_S, find_events, signed_residual
from synodic.time_data import TimeData, calendar_string

ROOT = Path(__file__).resolve().parent


def main():
    td = TimeData.read(ROOT / "data/leap-seconds.list")
    ts = td.ts
    fixtures = ROOT / "tests/fixtures"
    output = ROOT / "output/1926-2126"
    data = json.loads((output / "results.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, checksum in manifest["output_sha256"].items():
        assert sha256(output / name) == checksum, name
    rows = data["events"]
    for row in rows:
        datetime.fromisoformat(row["tt"])
        datetime.fromisoformat(row["ut1_estimate"])
        assert row["numerical_bracket_seconds"] <= .001
        assert abs(row["longitude_residual_arcseconds"]) < .0004
        if row["utc_status"] != "within_leap_table_validity":
            assert row["utc"] is None
    assert all(x["phase"] != y["phase"] for x, y in zip(rows, rows[1:]))
    assert all(x["tt"] < y["tt"] for x, y in zip(rows, rows[1:]))
    pairs = data["lunations"]
    for row in pairs:
        assert row["new_tt"] < row["full_tt"] < row["next_new_tt"]
        assert 29.2 < row["length_tt_days"] < 29.9
        assert 13 < row["new_to_full_tt_days"] < 17
    assert all(x["next_new_tt"] == y["new_tt"] for x, y in zip(pairs, pairs[1:]))
    usno = []
    angular = []
    timing = []
    eph = load_file(str(ROOT / "data/de440s.bsp"))
    try:
        phase_names = ("New Moon", "First Quarter", "Full Moon", "Last Quarter")
        for year in (1926, 1980, 2000, 2024, 2100):
            scale = "utc" if 1972 <= year <= 2024 else "ut1"
            boundary = getattr(ts, scale)
            events = find_events(eph, ts, boundary(year, 1, 1), boundary(year + 1, 1, 1))
            refs = json.loads((fixtures / f"usno-{year}.json").read_text())["phasedata"]
            assert len(events) == len(refs)
            differences = []
            for e, ref in zip(events, refs):
                assert phase_names[e.phase] == ref["phase"]
                ref_dt = datetime.fromisoformat(f'{year}-{ref["month"]:02d}-{ref["day"]:02d}T{ref["time"]}:00')
                actual = e.time.utc_iso(places=3).removesuffix("Z") if scale == "utc" else calendar_string(e.time, "ut1")
                differences.append((datetime.fromisoformat(actual) - ref_dt).total_seconds())
            max_diff = max(abs(v) for v in differences)
            assert max_diff < (120 if year == 2100 else 60)
            usno.append({"year": year, "events": len(events), "comparison_scale": scale,
                         "max_abs_difference_seconds": max_diff,
                         "mean_signed_difference_seconds": float(np.mean(differences))})
        for row in json.loads((fixtures / "horizons-samples.json").read_text())["samples"]:
            jd = Decimal(row["tt_jd"])
            t = ts.tt_jd(int(jd), float(jd - int(jd)))
            reference = (row["moon_longitude_degrees"] - row["sun_longitude_degrees"]) % 360
            residual = abs(signed_residual(reference, row["phase"] * 90)) * 3600
            # Local derivative converts the angular mismatch to an approximate
            # event-time difference. It is not an observed absolute error.
            speed = abs(signed_residual(moon_phase(eph, t + 1 / DAY_S).degrees,
                                        moon_phase(eph, t - 1 / DAY_S).degrees)) * 3600 / 2
            angular.append(residual)
            timing.append(residual / speed)
        assert max(angular) < .02
    finally:
        eph.close()
    report = {
        "passed": True, "events_checked": len(rows), "lunations_checked": len(pairs),
        "kernel_sha256": sha256(ROOT / "data/de440s.bsp"),
        "input_results_sha256": sha256(output / "results.json"),
        "usno_minute_resolution_checks": usno,
        "horizons": {"samples": len(angular), "max_phase_residual_arcseconds": max(angular),
                     "max_equivalent_time_difference_seconds": max(timing),
                     "interpretation": "Cross-model agreement at sampled epochs, not a physical-error bound."},
        "numerical_solver": manifest["solver"],
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
