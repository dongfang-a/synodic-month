from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from skyfield.api import load_file

from . import __version__
from .engine import DAY_S, PHASE_NAMES, PHASE_ZH, find_events, inside, pair_lunations
from .time_data import TimeData, time_fields

KERNEL_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
LEAP_URL = "https://data.iana.org/time-zones/data/leap-seconds.list"


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def download(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open("wb") as dest:
            while chunk := source.read(1024 * 1024):
                dest.write(chunk)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD.") from exc


def build_parser():
    parser = argparse.ArgumentParser(description="JPL 朔望时刻与实际朔望月长度；不计算农历日期或概率。")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("prepare", help="下载 DE440s 与 IANA/IERS 闰秒表；已有文件保留")
    fetch.add_argument("--data-dir", type=Path, default=Path("data"))
    fetch.add_argument("--refresh-leaps", action="store_true")
    calc = sub.add_parser("calculate", help="离线计算，默认 1926-09-29 至 2126-09-29")
    calc.add_argument("--start", type=parse_date, default=date(1926, 9, 29))
    calc.add_argument("--end", type=parse_date, default=date(2126, 9, 29))
    calc.add_argument("--boundary-scale", choices=("tt", "ut1", "utc"), default="tt",
                      help="输入日期的时间尺度；默认 TT，左闭右开")
    calc.add_argument("--kernel", type=Path, default=Path("data/de440s.bsp"))
    calc.add_argument("--leaps", type=Path, default=Path("data/leap-seconds.list"))
    calc.add_argument("--out", type=Path, default=Path("output/1926-2126"))
    calc.add_argument("--tolerance", type=float, default=0.001, help="数值包围区间宽度（秒），不是实际误差")
    calc.add_argument("--offset-hours", type=float, default=8.0, help="固定 UTC 偏移；默认 +8，不使用夏令时")
    calc.add_argument("--all-phases", action="store_true", help="事件表也列出上弦、下弦")
    calc.add_argument("--overwrite", action="store_true", help="替换本程序已有输出文件")
    return parser


def calculate(args):
    tic = time.perf_counter()
    if not args.start < args.end:
        raise ValueError("Start must precede end.")
    if not -24 < args.offset_hours < 24:
        raise ValueError("UTC offset must be strictly between -24 and +24 hours.")
    td = TimeData.read(args.leaps)
    ts = td.ts
    def boundary(d):
        return getattr(ts, args.boundary_scale)(d.year, d.month, d.day)
    start, end = boundary(args.start), boundary(args.end)
    if args.boundary_scale == "utc" and (
        td.utc_status(start) != "within_leap_table_validity"
        or td.utc_status(end - 1 / DAY_S) != "within_leap_table_validity"
    ):
        raise ValueError("UTC boundaries require valid leap-table coverage from 1972. Use TT or UT1 for other dates.")
    names = ("events.csv", "lunations.csv", "results.json", "manifest.json")
    if not args.overwrite and any((args.out / n).exists() for n in names):
        raise ValueError("Output already exists. Select another --out or pass --overwrite.")
    eph = load_file(str(args.kernel))
    try:
        last_update = [0.0]
        def progress(n, total):
            now = time.perf_counter()
            if n == total or now - last_update[0] >= 10:
                print(f"计算进度 {n}/{total}", file=sys.stderr, flush=True)
                last_update[0] = now
        # Padding also preserves the initial full moon's preceding new moon.
        events = find_events(eph, ts, start - 32, end + 32,
                             tolerance_seconds=args.tolerance, progress=progress)
        pairs = pair_lunations(events, start, end)
        all_fields = [time_fields(e.time, td, args.offset_hours) for e in events]
        fields_by_id = {id(e): f for e, f in zip(events, all_fields)}
        previous_new = None
        event_rows = []
        for e in events:
            if e.phase == 0:
                previous_new = fields_by_id[id(e)]["tt"]
            if inside(e.time, start, end) and (args.all_phases or e.phase in (0, 2)):
                event_rows.append({
                    "phase": PHASE_NAMES[e.phase], "phase_zh": PHASE_ZH[e.phase],
                    **fields_by_id[id(e)], "preceding_new_tt": previous_new,
                    "numerical_bracket_seconds": e.bracket_seconds,
                    "longitude_residual_arcseconds": e.residual_arcseconds,
                })
        lunation_rows = []
        selected_fields = ("tt", "utc", "local_fixed_offset", "utc_provisional",
                           "local_fixed_offset_provisional", "ut1_estimate", "utc_status")
        for new, full, nxt in pairs:
            row = {}
            for prefix, e in (("new", new), ("full", full), ("next_new", nxt)):
                row.update({prefix + "_" + k: fields_by_id[id(e)][k] for k in selected_fields})
            row.update({
                "new_to_full_tt_days": float(full.time - new.time),
                "length_tt_days": float(nxt.time - new.time),
                "length_tt_seconds": float(nxt.time - new.time) * DAY_S,
                "full_inside_requested_interval": bool(inside(full.time, start, end)),
                "next_new_inside_requested_interval": bool(inside(nxt.time, start, end)),
            })
            lunation_rows.append(row)
        delta_file = Path(__import__("skyfield").__file__).parent / "data" / "iers.npz"
        manifest = {
            "schema_version": 1, "program_version": __version__,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "request": {"start": args.start.isoformat(), "end_exclusive": args.end.isoformat(),
                        "boundary_scale": args.boundary_scale, "fixed_utc_offset_hours": args.offset_hours,
                        "all_phases": args.all_phases},
            "definition": "Geocentric apparent Moon minus Sun ecliptic longitude of date: new=0, full=180 degrees.",
            "model": "Skyfield observe().apparent(), ecliptic of date, default full IAU 2000A nutation; JPL SPK",
            "kernel": {"file": args.kernel.name, "sha256": sha256(args.kernel),
                       "size_bytes": args.kernel.stat().st_size,
                       "segments": str(eph)},
            "leaps": {"file": args.leaps.name, "sha256": sha256(args.leaps),
                      "expires_utc_exclusive": td.expires.isoformat(),
                      "updated_utc": td.updated.isoformat() if td.updated else None,
                      "last_tai_minus_utc_seconds": float(ts.leap_offsets[-1])},
            "delta_t": {"source": "Skyfield builtin iers.npz plus its historical/prediction model",
                        "file_sha256": sha256(delta_file),
                        "table_tt_jd_range": [float(ts.delta_t_table[0][0]), float(ts.delta_t_table[0][-1])],
                        "ut1_is_model_dependent": True},
            "solver": {"method": "2-day scan, vectorized bisection with two-part TT JD, 366-day chunks",
                       "max_requested_bracket_seconds": args.tolerance,
                       "max_actual_bracket_seconds": max((e.bracket_seconds for e in events), default=None),
                       "max_abs_longitude_residual_arcseconds": max((abs(e.residual_arcseconds) for e in events), default=None)},
            "counts": dict(Counter(r["phase"] for r in event_rows)),
            "lunations": len(lunation_rows),
            "utc_status_counts": dict(Counter(r["utc_status"] for r in event_rows)),
            "length_tt_days_min": min((r["length_tt_days"] for r in lunation_rows), default=None),
            "length_tt_days_max": max((r["length_tt_days"] for r in lunation_rows), default=None),
            "accuracy_notes": [
                "Numerical bracket width and printed digits are not physical accuracy guarantees.",
                "TT phase times depend on the ephemeris and apparent-position model; no absolute error bound is asserted.",
                "UTC fields are empty before 1972 and after leap-table expiry. Future UTC projections have separate provisional fields, holding the last TAI-UTC offset constant.",
                "UT1 estimates depend on Delta T; historical and future values are not exact civil times.",
                "Fixed local offset is not a historical timezone or a future civil-time policy prediction.",
                "Lunations are selected by initial new moon; full/next-new may be outside the requested interval.",
                "No Chinese calendar dates or fifteen/sixteen probabilities are computed.",
            ],
            "software": {name: importlib.metadata.version(name) for name in ("skyfield", "numpy", "jplephem", "sgp4")},
            "python": platform.python_version(), "elapsed_seconds": time.perf_counter() - tic,
            "sources": [KERNEL_URL, LEAP_URL, "https://aa.usno.navy.mil/faq/moon_phases",
                        "https://ssd.jpl.nasa.gov/doc/de440_de441.html"],
        }
    finally:
        eph.close()
    args.out.mkdir(parents=True, exist_ok=True)
    event_columns = ["phase", "phase_zh", *time_fields(start, td, args.offset_hours),
                     "preceding_new_tt", "numerical_bracket_seconds", "longitude_residual_arcseconds"]
    lunation_columns = [f"{p}_{k}" for p in ("new", "full", "next_new") for k in selected_fields]
    lunation_columns += ["new_to_full_tt_days", "length_tt_days", "length_tt_seconds",
                         "full_inside_requested_interval", "next_new_inside_requested_interval"]
    write_csv(args.out / "events.csv", event_rows, event_columns)
    write_csv(args.out / "lunations.csv", lunation_rows, lunation_columns)
    (args.out / "results.json").write_text(json.dumps(
        {"manifest": manifest, "events": event_rows, "lunations": lunation_rows},
        ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    manifest["output_sha256"] = {n: sha256(args.out / n) for n in names if n != "manifest.json"}
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"完成：{len(event_rows)} 个事件，{len(lunation_rows)} 个完整朔望月。输出：{args.out.resolve()}")
    print("注意：未来 UTC 仅在 provisional 字段中提供；毫秒求解容差不代表毫秒天文准确度。")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            for url, name in ((KERNEL_URL, "de440s.bsp"), (LEAP_URL, "leap-seconds.list")):
                path = args.data_dir / name
                if not path.exists() or (name == "leap-seconds.list" and args.refresh_leaps):
                    print(f"Downloading {url}", flush=True)
                    download(url, path)
                print(f"{path}: sha256={sha256(path)}")
            TimeData.read(args.data_dir / "leap-seconds.list")
        else:
            calculate(args)
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
