"""Explicit time scales and conservative UTC validity, with no silent downloads."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from math import floor

import numpy as np
from skyfield.api import load
from skyfield.timelib import Timescale

DAY_S = 86400.0
NTP_EPOCH = datetime(1900, 1, 1, tzinfo=timezone.utc)


@dataclass
class TimeData:
    ts: Timescale
    leap_file: Path
    expires: datetime
    updated: datetime | None

    @classmethod
    def read(cls, path):
        path = Path(path)
        dates, offsets = [], []
        expiry = updated = None
        for line in path.read_text(encoding="ascii").splitlines():
            if line.startswith("#@"):
                expiry = NTP_EPOCH + timedelta(seconds=int(line[2:].split()[0]))
            elif line.startswith("#$"):
                updated = NTP_EPOCH + timedelta(seconds=int(line[2:].split()[0]))
            elif line.strip() and not line.lstrip().startswith("#"):
                ntp, offset = line.split()[:2]
                dates.append(2415020.5 + int(ntp) / DAY_S)
                offsets.append(int(offset))
        if expiry is None or not dates or dates[0] != 2441317.5 or offsets[0] != 10:
            raise ValueError("Invalid leap-seconds.list: need expiry and table starting 1972-01-01.")
        if not np.all(np.diff(dates) > 0) or not np.all(np.abs(np.diff(offsets)) == 1):
            raise ValueError("Leap-second entries must be ordered, with offsets changing by one second.")
        expiry_jd = 2415020.5 + (expiry - NTP_EPOCH).total_seconds() / DAY_S
        if expiry_jd <= dates[-1]:
            raise ValueError("Leap-second expiry must follow the last entry.")
        base = load.timescale(builtin=True)
        ts = Timescale(base.delta_t_table, np.array(dates), np.array(offsets, dtype=float))
        return cls(ts, path, expiry, updated)

    def utc_status(self, t):
        if t < self.ts.utc(1972, 1, 1):
            return "unavailable_before_1972"
        if not t < self.ts.from_datetime(self.expires):
            return "provisional_constant_tai_minus_utc"
        return "within_leap_table_validity"


def calendar_string(t, scale):
    """Round a non-UTC calendar to milliseconds without platform strftime %f."""
    y, m, d, h, minute, second = getattr(t, scale + "_calendar")()
    base = datetime(int(y), int(m), int(d), int(h), int(minute))
    return (base + timedelta(milliseconds=round(float(second) * 1000))).isoformat(timespec="milliseconds")


def time_fields(t, time_data, offset_hours=8):
    status = time_data.utc_status(t)
    out = {
        "tt": calendar_string(t, "tt"),
        "tt_jd_whole": int(t.whole) + floor(t.tt_fraction),
        "tt_jd_fraction": float(t.tt_fraction) - floor(t.tt_fraction),
        "tdb_jd_whole": int(t.whole) + floor(t.tdb_fraction),
        "tdb_jd_fraction": float(t.tdb_fraction) - floor(t.tdb_fraction),
        "ut1_estimate": calendar_string(t, "ut1"),
        "delta_t_seconds": float(t.delta_t),
        "utc": None,
        "local_fixed_offset": None,
        "utc_provisional": None,
        "local_fixed_offset_provisional": None,
        "utc_status": status,
    }
    if status != "unavailable_before_1972":
        # Preserve an actual leap second in UTC; datetime alone cannot represent it.
        utc = t.utc_iso(places=3)
        local, leap = t.astimezone_and_leap_second(timezone(timedelta(hours=offset_hours)))
        local_text = local.isoformat(timespec="milliseconds") if not leap else None
        suffix = "" if status == "within_leap_table_validity" else "_provisional"
        out["utc" + suffix] = utc
        out["local_fixed_offset" + suffix] = local_text
    return out
