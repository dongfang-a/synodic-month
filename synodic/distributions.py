"""Offline empirical distributions from the existing, paired lunation records."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from math import floor, isfinite

EAST_EIGHT = timezone(timedelta(hours=8))
DAY_NAMES = {14: "十四", 15: "十五", 16: "十六", 17: "十七", 18: "十八"}


def civil_time(record, prefix):
    """Fixed +08:00, explicitly retaining the source time conversion for each event."""
    status = record[prefix + "_utc_status"]
    if status == "within_leap_table_validity":
        raw = record[prefix + "_utc"]
        label = "UTC+08:00"
    elif status == "provisional_constant_tai_minus_utc":
        raw = record[prefix + "_utc_provisional"]
        label = "provisional_UTC+08:00"
    elif status == "unavailable_before_1972":
        raw = record[prefix + "_ut1_estimate"]
        # A clock label, not an assertion that historic UT1 was UTC.
        return (datetime.fromisoformat(raw) + timedelta(hours=8)).replace(tzinfo=EAST_EIGHT), "UT1_estimate+08:00"
    else:
        raise ValueError(f"Unknown UTC status: {status}")
    if not raw:
        raise ValueError(f"Missing {prefix} timestamp for status {status}")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(EAST_EIGHT), label


def derive_sample(record, index):
    new, new_basis = civil_time(record, "new")
    full, full_basis = civil_time(record, "full")
    lunar_day = (full.date() - new.date()).days + 1
    minutes = float(record["new_to_full_tt_days"]) * 1440.0
    if not isfinite(minutes) or minutes <= 0:
        raise ValueError("The TT interval must be positive and finite.")
    midnight = datetime.combine(new.date(), datetime.min.time(), tzinfo=EAST_EIGHT)
    if not 14 <= lunar_day <= 17:
        raise ValueError(f"A full moon falls outside lunar days 14--17: {full.isoformat()}, day {lunar_day}")
    return {
        "sample": index,
        "new_tt": record["new_tt"],
        "full_tt": record["full_tt"],
        "new_east8_clock": new.isoformat(timespec="milliseconds"),
        "full_east8_clock": full.isoformat(timespec="milliseconds"),
        "new_clock_basis": new_basis,
        "full_clock_basis": full_basis,
        "interval_tt_minutes": minutes,
        "interval_bin_start_minute": floor(minutes),
        "lunar_day": lunar_day,
        "full_clock_hour": full.hour,
        "full_clock_time": full.strftime("%H:%M:%S") + f".{full.microsecond // 1000:03d}",
        "hours_from_day14_midnight": (full - midnight).total_seconds() / 3600 - 13 * 24,
        "hour_bin_start_from_day14": (lunar_day - 14) * 24 + full.hour,
    }


def lunar_hour_label(hour):
    day, h = divmod(int(hour), 24)
    return f"{DAY_NAMES[14 + day]} {h:02d}:00"


def analyse(document):
    selected = [row for row in document["lunations"] if row["full_inside_requested_interval"]]
    if not selected:
        raise ValueError("No full-moon samples inside the requested interval.")
    samples = [derive_sample(row, i + 1) for i, row in enumerate(selected)]
    n = len(samples)
    minutes = Counter(s["interval_bin_start_minute"] for s in samples)
    hours = Counter(s["hour_bin_start_from_day14"] for s in samples)
    days = Counter(s["lunar_day"] for s in samples)
    minute_bins = [
        {"left_minute": k, "right_minute_exclusive": k + 1, "count": minutes[k], "probability": minutes[k] / n}
        for k in range(min(minutes), max(minutes) + 1)
    ]
    hour_bins = [
        {"left_hour_from_day14": k, "right_hour_exclusive": k + 1,
         "lunar_day": 14 + k // 24, "clock_hour": k % 24,
         "left_label": lunar_hour_label(k), "right_label_exclusive": lunar_hour_label(k + 1),
         "count": hours[k], "probability": hours[k] / n,
         "shown_in_chart": min(hours) <= k <= max(hours)}
        for k in range(96)
    ]
    day_bins = [{"lunar_day": day, "label": DAY_NAMES[day], "count": days[day], "probability": days[day] / n}
                for day in range(14, 18)]
    return {"samples": samples, "minute_bins": minute_bins, "hour_bins": hour_bins, "day_bins": day_bins}
