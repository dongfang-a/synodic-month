"""Explicit, optional network step to refresh independent JPL validation fixtures.

Run from the project root: python tests/fetch_horizons.py
Tests themselves are offline. Horizons currently uses DE441 and IAU76/80 for
quantity 31, so agreement checks are cross-model comparisons, not identity.
"""
import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from skyfield.api import load_file

from synodic.engine import find_events
from synodic.time_data import TimeData

ROOT = Path(__file__).resolve().parents[1]
td = TimeData.read(ROOT / "data/leap-seconds.list")
ts = td.ts
requests = []
eph = load_file(str(ROOT / "data/de440s.bsp"))
try:
    for year in (1926, 1980, 2000, 2024, 2100, 2126):
        events = find_events(eph, ts, ts.tt(year, 1, 1), ts.tt(year, 2, 1))[:4]
        for e in events:
            jd = Decimal(str(float(e.time.whole))) + Decimal(str(float(e.time.tt_fraction)))
            requests.append({"tt_jd": str(jd), "phase": e.phase})
finally:
    eph.close()
folder = ROOT / "tests/fixtures"
longitudes = {}
for body, name in ((301, "moon"), (10, "sun")):
    params = {"COMMAND": str(body), "CENTER": "500@399", "MAKE_EPHEM": "YES",
              "EPHEM_TYPE": "OBSERVER", "TLIST": ",".join(r["tt_jd"] for r in requests),
              "TIME_TYPE": "TT", "QUANTITIES": "31", "CSV_FORMAT": "YES",
              "EXTRA_PREC": "YES", "CAL_FORMAT": "JD", "TIME_DIGITS": "FRACSEC"}
    query = {k: "'" + v + "'" for k, v in params.items()}
    query["format"] = "json"
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(query)
    raw = urllib.request.urlopen(url, timeout=60).read()
    data = json.loads(raw)
    if "error" in data or "$$SOE" not in data.get("result", ""):
        raise RuntimeError(data)
    (folder / f"horizons-{name}.json").write_bytes(raw)
    table = data["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
    rows = list(csv.reader(table.splitlines()))
    assert len(rows) == len(requests)
    longitudes[name] = [float(row[3]) for row in rows]
    print(name, len(rows), flush=True)
for i, request in enumerate(requests):
    request.update({name + "_longitude_degrees": values[i] for name, values in longitudes.items()})
snapshot = {"retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "source": "https://ssd.jpl.nasa.gov/api/horizons.api",
            "center": "500@399", "quantity": 31, "time_type": "TT",
            "notes": "Independent DE441/IAU76-80 apparent ecliptic longitude; raw responses retained.",
            "samples": requests}
(folder / "horizons-samples.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
print("Saved", len(requests), "independent apparent-longitude samples.")
