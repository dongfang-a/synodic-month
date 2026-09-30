r"""Reproduce the requested 1-minute and 1-hour figures without new ephemeris work.

Run: .venv\Scripts\python.exe -X utf8 analyze.py
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from synodic.distributions import DAY_NAMES, analyse, lunar_hour_label

ROOT = Path(__file__).resolve().parent


def checksum(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def duration_label(minutes, seconds=False):
    total = round(minutes * 60)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minute, second = divmod(remainder, 60)
    text = f"{days}天{hours:02d}时{minute:02d}分"
    return text + (f"{second:02d}秒" if seconds else "")


def configure_plotting():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    font = next((p for p in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")) if p.exists()), None)
    if font:
        font_manager.fontManager.addfont(str(font))
        family = font_manager.FontProperties(fname=str(font)).get_name()
    else:
        available = {entry.name for entry in font_manager.fontManager.ttflist}
        family = next((name for name in ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "PingFang SC") if name in available), None)
        if family is None:
            raise RuntimeError("A Chinese font is required: Microsoft YaHei or Noto Sans CJK SC.")
    matplotlib.rcParams.update({
        "font.family": family, "font.size": 11, "axes.unicode_minus": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#B8C4CF", "axes.labelcolor": "#273E50",
        "xtick.color": "#405364", "ytick.color": "#405364",
        "svg.fonttype": "path", "savefig.facecolor": "white",
    })
    return family


def draw_figures(data, summary, out):
    family = configure_plotting()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MultipleLocator, PercentFormatter

    ink, muted, blue = "#19374A", "#526879", "#246D9B"
    colors = {14: "#9CAEC4", 15: "#4E86B5", 16: "#137F7D", 17: "#C88D43"}
    n = len(data["samples"])
    request = summary["source_request"]
    subtitle = f"{n:,} 个样本  ·  望落在 {request['start']} 至 {request['end_exclusive']} 的原计算区间内"

    def canvas(title, details):
        fig, ax = plt.subplots(figsize=(16, 7.6), dpi=120)
        fig.subplots_adjust(left=.08, right=.975, bottom=.21, top=.70)
        fig.text(.08, .93, title, fontsize=24, weight="bold", color=ink)
        fig.text(.08, .88, subtitle, fontsize=11, color=muted)
        fig.text(.08, .825, details, fontsize=12, color=ink)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#E3EAF0", linewidth=.8)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=2))
        ax.tick_params(axis="both", length=3.5, pad=8)
        return fig, ax

    minutes = [s["interval_tt_minutes"] for s in data["samples"]]
    details = (f"最短  {duration_label(min(minutes), True)}     "
               f"平均  {duration_label(sum(minutes) / n, True)}     "
               f"最长  {duration_label(max(minutes), True)}")
    fig, ax = canvas("朔到望，需要多长时间？", details)
    bins = data["minute_bins"]
    ax.bar([b["left_minute"] for b in bins], [b["probability"] for b in bins], width=1,
           align="edge", color=blue, edgecolor="none", linewidth=0)
    ax.set_xlim(bins[0]["left_minute"], bins[-1]["right_minute_exclusive"])
    ax.set_ylim(0, max(b["probability"] for b in bins) * 1.15)
    ax.xaxis.set_major_locator(MultipleLocator(360))
    ax.xaxis.set_minor_locator(MultipleLocator(60))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{int(value) // 1440}天\n{int(value) % 1440 // 60:02d}小时"))
    ax.set_xlabel("朔 → 望的实际时间间隔（TT）", labelpad=13)
    ax.set_ylabel("每 1 分钟区间的概率", labelpad=13)
    fig.text(.08, .085, "每根柱子宽 1 分钟；柱高 = 该分钟格的样本数 ÷ 2,473。所有柱子的概率合计为 100%。", color=muted, fontsize=10)
    fig.text(.08, .045, "按实际事件时刻直接分箱，不先四舍五入；未平滑，也未合并分钟格。", color=muted, fontsize=10)
    for extension in ("png", "svg"):
        fig.savefig(out / f"01_new_to_full_1minute.{extension}", dpi=300)
    plt.close(fig)

    details = "    ·    ".join(f"{row['label']}  {row['count']:,} 次 / {row['probability']:.2%}" for row in data["day_bins"])
    fig, ax = canvas("望，落在农历哪一天、几点？", details)
    visible = [b for b in data["hour_bins"] if b["shown_in_chart"]]
    left, right = visible[0]["left_hour_from_day14"], visible[-1]["right_hour_exclusive"]
    for day in range(14, 18):
        a, b = max(left, (day - 14) * 24), min(right, (day - 13) * 24)
        if a < b:
            ax.axvspan(a, b, color=colors[day], alpha=.065, linewidth=0)
    ax.bar([b["left_hour_from_day14"] + .08 for b in visible], [b["probability"] for b in visible],
           width=.84, align="edge", color=[colors[b["lunar_day"]] for b in visible], edgecolor="none")
    for boundary in (24, 48, 72):
        if left < boundary < right:
            ax.axvline(boundary, color="#A9BAC7", linewidth=.9, linestyle=(0, (3, 3)))
    ax.set_xlim(left, right)
    ax.set_ylim(0, max(b["probability"] for b in visible) * 1.14)
    ticks = sorted(set([left, right] + [k for k in range(0, 97, 6) if left < k < right]))
    def tick_label(k):
        day, hour = 14 + k // 24, k % 24
        return (f"{DAY_NAMES[day]}\n{hour:02d}:00" if k == left or hour == 0 else f"{hour:02d}:00")
    ax.set_xticks(ticks, [tick_label(k) for k in ticks], fontsize=10)
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    ax.set_xlabel("东八区农历日期与时刻（初一从朔所在日的 00:00 开始）", labelpad=13)
    ax.set_ylabel("每 1 小时区间的概率", labelpad=13)
    fig.text(.08, .085, f"每格 1 小时，分母统一为 2,473；显示 {lunar_hour_label(left)} 至 {lunar_hour_label(right)}，右端不含。", color=muted, fontsize=10)
    fig.text(.08, .045, "仅裁掉这批样本中两端的零计数小时；早期用 UT1+8，现代用 UTC+8，未来沿用已有 UTC 投影+8。", color=muted, fontsize=10)
    for extension in ("png", "svg"):
        fig.savefig(out / f"02_full_moon_lunar_day_1hour.{extension}", dpi=300)
    plt.close(fig)
    return family


def main(argv=None):
    parser = argparse.ArgumentParser(description="用已有 200 年数据生成朔望间隔和望的农历时刻分布")
    parser.add_argument("--source", type=Path, default=ROOT / "output/1926-2126/results.json")
    parser.add_argument("--out", type=Path, default=ROOT / "output/1926-2126/distributions")
    args = parser.parse_args(argv)
    document = json.loads(args.source.read_text(encoding="utf-8"))
    source_manifest = args.source.parent / "manifest.json"
    if source_manifest.exists():
        expected = json.loads(source_manifest.read_text(encoding="utf-8"))["output_sha256"][args.source.name]
        if checksum(args.source) != expected:
            raise ValueError("Source results do not match the recorded SHA-256.")
    data = analyse(document)
    if len(data["samples"]) != 2473:
        raise ValueError("This requested analysis requires exactly 2,473 samples.")
    expected_full = sorted(row["tt"] for row in document["events"] if row["phase"] == "full")
    if sorted(s["full_tt"] for s in data["samples"]) != expected_full:
        raise ValueError("Selected paired full moons do not match the event table.")
    n = len(data["samples"])
    for key in ("minute_bins", "hour_bins", "day_bins"):
        if sum(b["count"] for b in data[key]) != n or not math.isclose(sum(b["probability"] for b in data[key]), 1, abs_tol=1e-12):
            raise ValueError(f"Probability/quantity conservation failed for {key}.")
    intervals = [s["interval_tt_minutes"] for s in data["samples"]]
    occupied = [b for b in data["hour_bins"] if b["count"]]
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_results_sha256": checksum(args.source),
        "source_request": document["manifest"]["request"],
        "sample_count": n, "excluded_lunations": len(document["lunations"]) - n,
        "selection": "Paired lunations whose full moon is inside the original TT half-open interval.",
        "probability": "count / 2473 in every bin, no smoothing, no conditional renormalization by lunar day",
        "bin_closure": "left inclusive, right exclusive; classify before rounding",
        "east8_rule": "Fixed +8; before 1972 UT1 estimate, valid UTC where available, otherwise existing provisional UTC.",
        "lunar_day_rule": "Difference of east-eight civil calendar dates (full minus new) + 1; civil day begins at midnight.",
        "interval": {"bin_minutes": 1, "bin_count": len(data["minute_bins"]),
                     "zero_count_bins": sum(b["count"] == 0 for b in data["minute_bins"]),
                     "minimum_minutes": min(intervals), "maximum_minutes": max(intervals),
                     "mean_minutes": sum(intervals) / n},
        "full_moon": {"bin_hours": 1, "all_bins": 96,
                      "shown_bins": sum(b["shown_in_chart"] for b in data["hour_bins"]),
                      "display_start": occupied[0]["left_label"],
                      "display_end_exclusive": occupied[-1]["right_label_exclusive"],
                      "earliest_lunar_position_hours_from_day14": min(s["hours_from_day14_midnight"] for s in data["samples"]),
                      "latest_lunar_position_hours_from_day14": max(s["hours_from_day14_midnight"] for s in data["samples"]),
                      "outside_days14_to17": 0, "by_lunar_day": data["day_bins"],
                      "clock_basis_counts": dict(Counter(s["full_clock_basis"] for s in data["samples"]))},
        "notes": ["Empirical frequencies in this finite sample, not universal theoretical probabilities.",
                  "Cropped empty hours are absent in this sample, not proven physically impossible for all epochs.",
                  "TT determines elapsed duration; east-eight civil date differences determine lunar day.",
                  "Historical timezone/DST reconstruction, lunar month names and intercalary-month placement are not used."],
        "sources": ["https://www.pmo.cas.cn/xwdt2019/kpdt2019/202203/t20220317_6399980.html"],
        "matplotlib_version": importlib.metadata.version("matplotlib"),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for filename, key in (("samples.csv", "samples"), ("interval_bins_1minute.csv", "minute_bins"),
                          ("full_moon_bins_1hour.csv", "hour_bins"), ("lunar_day_totals.csv", "day_bins")):
        write_csv(args.out / filename, data[key])
    summary["font"] = draw_figures(data, summary, args.out)
    summary["analysis_source_sha256"] = {"analyze.py": checksum(__file__), "synodic/distributions.py": checksum(ROOT / "synodic/distributions.py")}
    summary["output_sha256"] = {p.name: checksum(p) for p in sorted(args.out.iterdir()) if p.suffix in (".png", ".svg", ".csv")}
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "README.md").write_text(
        "# 朔到望间隔与望的农历时刻分布\n\n"
        "两张图使用相同的 2,473 个样本：望在原 TT 区间 [1926-09-29, 2126-09-29) 内。"
        "月表中最后一个望在 2126-10-01 的周期排除；不重新计算天文历表。\n\n"
        "- `01_new_to_full_1minute.png/svg`：朔到望的 TT 间隔，每分钟一个格。\n"
        "- `02_full_moon_lunar_day_1hour.png/svg`：东八区农历十四至十七，每小时一个格；"
        f"仅显示 {summary['full_moon']['display_start']} 至 {summary['full_moon']['display_end_exclusive']}（右端不含）。\n"
        "- `samples.csv`：逐样本的朔、望时刻、时间换算依据、农历日序与所归分箱。\n"
        "- `interval_bins_1minute.csv`：每分钟格的计数与概率，保留中间零计数格。\n"
        "- `full_moon_bins_1hour.csv`：完整 96 个小时格，`shown_in_chart` 标记是否绘制。\n"
        "- `lunar_day_totals.csv`：十四、十五、十六、十七的总计数和概率。\n"
        "- `summary.json`：统计口径、样本量、时间范围、软件版本及文件 SHA-256。\n\n"
        "概率统一为计数除以 2,473，不按日期分别归一化，不做平滑。区间左闭右开，先分箱后格式化。"
        "这些是给定 200 年样本的经验频率，不能把两端无样本等同于其他年代也绝不可能。\n\n"
        "农历日序 = 望与朔的东八区公历日期差 + 1。朔所在日从午夜起为初一，"
        "所以这不是将朔到望的持续时长直接取整。无须编排月份名称或闰月。"
        "固定采用 +8 小时，不重建历史时区或夏令时。1972 年前使用 UT1 估计，"
        "有效期内用 UTC，未来使用已有条件性 UTC 投影。\n\n"
        "重现：在项目根目录运行 `.venv\\Scripts\\python.exe -X utf8 analyze.py`。"
        "新增环境先安装 `pip install -e \".[analysis]\"`，并提供微软雅黑或 Noto Sans CJK SC 字体。\n\n"
        "日期规则参考：[紫金山天文台历书科普问题解答](https://www.pmo.cas.cn/xwdt2019/kpdt2019/202203/t20220317_6399980.html)。\n",
        encoding="utf-8")
    print(json.dumps({"output": str(args.out), "sample_count": n, "days": data["day_bins"],
                      "interval": summary["interval"], "display": [occupied[0]["left_label"], occupied[-1]["right_label_exclusive"]]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
