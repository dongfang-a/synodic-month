"""Explain why integrable endpoint singularities still have unit total area."""
import json
import math
from pathlib import Path

import numpy as np

from analyze import configure_plotting
from theory import parameters, cdf


def main():
    mu, amplitude = parameters()
    a, b = mu - amplitude, mu + amplitude
    # Forty bins are solely for a readable normalization illustration. The
    # original one-minute output is preserved unchanged.
    edges = np.linspace(a, b, 41)
    masses = np.diff(cdf(edges, mu, amplitude))
    widths = np.diff(edges)
    average_density = masses / widths
    area = float(np.sum(average_density * widths))
    assert math.isclose(area, 1, abs_tol=1e-14)
    assert np.all(np.isfinite(average_density))

    configure_plotting()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.1), dpi=120)
    fig.subplots_adjust(left=.075, right=.97, bottom=.23, top=.71, wspace=.23)
    ink, muted, teal = "#19374A", "#526879", "#137F7D"
    fig.text(.075, .935, "端点密度可以无限，总概率仍然是 1", color=ink, fontsize=23, weight="bold")
    fig.text(.075, .872, "同一个反正弦模型：有限区间的概率由积分计算，端点本身的概率为 0。", color=muted, fontsize=12)

    ax = axes[0]
    ax.bar(edges[:-1], average_density, width=widths, align="edge",
           color=teal, edgecolor="white", linewidth=.5, alpha=.85)
    ax.set_xlim(a, b)
    ax.set_ylim(0, average_density.max() * 1.15)
    ax.set_title("有限分箱后的平均概率密度", color=ink, fontsize=14, pad=18)
    ax.set_xlabel("朔到望的时间间隔（天）", labelpad=12)
    ax.set_ylabel("区间平均概率密度（每天）", labelpad=10)
    ax.text(.5, .65, "全部柱子的面积之和\nΣ（高度 × 宽度）= 1", ha="center", va="center",
            transform=ax.transAxes, color=ink, fontsize=13)

    ax = axes[1]
    x = np.linspace(a, b, 2000)
    ax.plot(x, cdf(x, mu, amplitude), color=teal, linewidth=2.5)
    ax.scatter([a, mu, b], [0, .5, 1], color=teal, s=40, zorder=3)
    ax.set_xlim(a - .03, b + .03)
    ax.set_ylim(-.04, 1.13)
    ax.set_title("累积概率：从 0 增长到 100%", color=ink, fontsize=14, pad=18)
    ax.set_xlabel("朔到望的时间间隔（天）", labelpad=12)
    ax.set_ylabel("不超过该间隔的概率", labelpad=10)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.annotate("最短处：0%", xy=(a, 0), xytext=(8, 13), textcoords="offset points", color=ink, fontsize=11)
    ax.annotate("最长处：100%", xy=(b, 1), xytext=(-7, 13), textcoords="offset points", ha="right", color=ink, fontsize=11)
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#E3EAF0", linewidth=.8)
    fig.text(.075, .12, f"为展示完整面积，左图分成 40 个等宽区间，每格约 {widths[0]*1440:.1f} 分钟；高度是该格概率除以格宽，未截断纵轴。", color=muted, fontsize=10)
    fig.text(.075, .073, "这是归一化原理示意，已有的一分钟分箱图表不变。两端较高来自余弦在极值附近变化较慢；仍属于简化模型。", color=muted, fontsize=10)
    folder = Path(__file__).resolve().parent / "output/theory"
    folder.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "svg"):
        fig.savefig(folder / f"density_normalization.{extension}", dpi=300)
    plt.close(fig)

    minute = 1 / 1440
    old_cap = 1.65
    crossing = math.sqrt(amplitude**2 - (1 / (math.pi * old_cap))**2)
    clipped_area = 2 * old_cap * (amplitude-crossing) + 2 / math.pi * math.asin(crossing/amplitude)
    results = {
        "explanation_bin_count": 40,
        "explanation_bin_width_minutes": float(widths[0]*1440),
        "displayed_total_area": area,
        "cdf_endpoints": [float(cdf(a,mu,amplitude)),float(cdf(b,mu,amplitude))],
        "probability_first_minute_from_exact_lower_support": float(cdf(a+minute,mu,amplitude)),
        "probability_minute_centered_on_mu": float(cdf(mu+minute/2,mu,amplitude)-cdf(mu-minute/2,mu,amplitude)),
        "previous_figure_capped_density_area_approx": clipped_area,
        "note": "Previous figure capped the density at 1.65/day and thus did not visibly display all area; this one does."
    }
    (folder / "density_normalization.json").write_text(json.dumps(results, indent=2),encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
