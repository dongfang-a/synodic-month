"""Find zeroes of geocentric apparent ecliptic longitude difference.

Two-part TT Julian dates are retained throughout bisection. Apparent positions
include Skyfield's light-time, aberration and gravitational-deflection model;
the ecliptic is of date, using Skyfield's default full IAU 2000A nutation.
"""
from dataclasses import dataclass

import numpy as np
from skyfield.almanac import moon_phase

DAY_S = 86400.0
PHASE_NAMES = ("new", "first_quarter", "full", "last_quarter")
PHASE_ZH = ("朔", "上弦", "望", "下弦")


@dataclass
class Event:
    time: object
    phase: int
    bracket_seconds: float
    residual_arcseconds: float


def signed_residual(angle, target):
    return (angle - target + 180.0) % 360.0 - 180.0


def inside(t, start, end):
    return not t < start and t < end


def check_coverage(eph, start, end):
    # Check all available segments conservatively, and allow retarded light-time
    # evaluation one day before reception. No extrapolation or fallback model.
    low = max(s.spk_segment.start_jd for s in eph.segments)
    high = min(s.spk_segment.end_jd for s in eph.segments)
    if float(start.tdb) - 1 < low or float(end.tdb) > high:
        raise ValueError(
            f"Requested interval including padding is outside kernel coverage "
            f"TDB JD [{low}, {high}]. Choose a wider kernel (e.g. de440.bsp)."
        )
    for body in ("earth", "moon", "sun"):
        eph[body]
    return low, high


def _search_chunk(eph, ts, start, end, tolerance_seconds, step_days):
    origin = float(start.whole)
    duration = float(end - start)
    x = float(start.tt_fraction) + np.linspace(0, duration, int(np.ceil(duration / step_days)) + 1)
    angles = moon_phase(eph, ts.tt_jd(origin, x)).degrees
    sectors = np.floor(angles / 90.0).astype(int)
    changed = np.flatnonzero(np.diff(sectors))
    if not len(changed):
        return []
    phases = sectors[changed + 1]
    if np.any((phases - sectors[changed]) % 4 != 1):
        raise RuntimeError("Scan skipped a phase; reduce step_days.")
    left, right = x[changed].copy(), x[changed + 1].copy()
    targets = phases * 90.0
    for _ in range(64):
        if np.max(right - left) * DAY_S <= tolerance_seconds:
            break
        middle = (left + right) / 2.0
        residual = signed_residual(moon_phase(eph, ts.tt_jd(origin, middle)).degrees, targets)
        before = residual < 0
        left = np.where(before, middle, left)
        right = np.where(before, right, middle)
    else:
        raise RuntimeError("Bisection failed to converge.")
    times = ts.tt_jd(origin, (left + right) / 2.0)
    residuals = signed_residual(moon_phase(eph, times).degrees, targets) * 3600.0
    return [Event(t, int(p), float(w * DAY_S), float(r))
            for t, p, w, r in zip(times, phases, right - left, residuals)]


def find_events(eph, ts, start, end, *, tolerance_seconds=0.001,
                chunk_days=366.0, step_days=2.0, progress=None):
    """All four phases in [start, end), in TT. Search tolerance is numerical only."""
    if not start < end:
        raise ValueError("Start must precede end.")
    if not np.isfinite(tolerance_seconds) or not 0.0001 <= tolerance_seconds <= 0.1:
        raise ValueError("Tolerance must be between 0.0001 and 0.1 seconds.")
    if not np.isfinite(step_days) or not 0 < step_days <= 2:
        raise ValueError("step_days must be in (0, 2].")
    if not np.isfinite(chunk_days) or chunk_days < step_days:
        raise ValueError("chunk_days must be finite and >= step_days.")
    check_coverage(eph, start - 1 / DAY_S, end + 1 / DAY_S)
    events = []
    chunks = int(np.ceil(float(end - start) / chunk_days))
    for i in range(chunks):
        a = start + i * chunk_days
        b = min(start + (i + 1) * chunk_days, end)
        # Overlap by one second. Deduplicate overlap roots using a margin far
        # below phase spacing, avoiding chunk-boundary losses/duplicates.
        found = _search_chunk(eph, ts, a - 1 / DAY_S, b + 1 / DAY_S,
                              tolerance_seconds, step_days)
        for e in found:
            if not inside(e.time, start, end):
                continue
            if events and abs(float(e.time - events[-1].time)) * DAY_S < 1:
                continue
            events.append(e)
        if progress:
            progress(i + 1, chunks)
    return events


def pair_lunations(events, start, end):
    """Lunations whose initial new moon is in [start,end); padded events required."""
    new_indices = [i for i, e in enumerate(events) if e.phase == 0]
    rows = []
    for i, j in zip(new_indices, new_indices[1:]):
        new, nxt = events[i], events[j]
        if not inside(new.time, start, end):
            continue
        full = [e for e in events[i + 1:j] if e.phase == 2]
        if len(full) != 1:
            raise RuntimeError("A lunation must contain exactly one full moon.")
        rows.append((new, full[0], nxt))
    # A missing padded next-new-moon must never silently discard a lunation.
    expected = sum(e.phase == 0 and inside(e.time, start, end) for e in events)
    if len(rows) != expected:
        raise RuntimeError("Insufficient end padding to complete the last lunation.")
    return rows
