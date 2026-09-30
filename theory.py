r"""Analytic, first-order lunar phase-interval model, independent of the dataset.

Run: .venv\Scripts\python.exe -X utf8 theory.py

Model: D(t) = w*t + 2*e*(sin(phi + n_a*t) - sin(phi)).
First order: T = mu - A*cos(phi + n_a*mu/2), phi uniform on [0,2*pi).
This is a model ensemble, not a high-precision dynamical ephemeris prediction.
"""
import csv
import json
import math
from pathlib import Path

import numpy as np

from analyze import configure_plotting

SYNODIC_DAYS = 29.530589
ANOMALISTIC_DAYS = 27.554550
ECCENTRICITY = 0.0549


def parameters():
    mu = SYNODIC_DAYS / 2
    w = 2 * math.pi / SYNODIC_DAYS
    na = 2 * math.pi / ANOMALISTIC_DAYS
    amplitude = 4 * ECCENTRICITY / w * abs(math.sin(na * mu / 2))
    return mu, amplitude


def cdf(t, mu, amplitude):
    z = np.clip((np.asarray(t) - mu) / amplitude, -1, 1)
    return .5 + np.arcsin(z) / np.pi


def main():
    output = Path(__file__).resolve().parent / "output/theory"
    output.mkdir(parents=True, exist_ok=True)
    mu, amplitude = parameters()
    a, b = mu - amplitude, mu + amplitude

    # Integrate the analytic CDF over every integer-minute bin. No simulated
    # random sample, no fit to observed extrema, and no Monte Carlo noise.
    edges = np.arange(math.floor(a * 1440), math.ceil(b * 1440) + 1, dtype=int)
    probabilities = np.diff(cdf(edges / 1440, mu, amplitude))
    if np.any(probabilities < 0) or not np.isclose(probabilities.sum(), 1, atol=1e-14):
        raise RuntimeError("The analytic probabilities do not sum to one.")
    with (output / "analytic_bins_1minute.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["left_minute", "right_minute_exclusive", "probability"])
        writer.writerows(zip(edges[:-1], edges[1:], probabilities))

    font = configure_plotting()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator, FuncFormatter

    # Endpoints have infinite density. Show a clearly marked finite vertical
    # viewport; export the complete finite one-minute masses above.
    z = np.linspace(-.99999, .99999, 20000)
    t = mu + amplitude * z
    density = 1 / (np.pi * amplitude * np.sqrt(1 - z*z))
    ink, muted, color = "#19374A", "#526879", "#137F7D"
    fig, ax = plt.subplots(figsize=(15, 7.2), dpi=120)
    fig.subplots_adjust(left=.085, right=.97, bottom=.23, top=.73)
    fig.text(.085, .93, "朔到望的理论分布：一个一阶近似模型", fontsize=22, weight="bold", color=ink)
    fig.text(.085, .87, "近点相位均匀分布  ·  固定平均轨道参数  ·  未使用已有样本拟合", fontsize=12, color=muted)
    fig.text(.085, .81, rf"$T=\mu+A\cos\theta,\quad \theta\sim U(0,2\pi)$" +
             f"     μ = {mu:.5f} 天，A = {amplitude:.5f} 天", fontsize=14, color=ink)
    ax.fill_between(t, density, color=color, alpha=.10)
    ax.plot(t, density, color=color, linewidth=2.8)
    ax.set_ylim(0, 1.65)
    ax.set_xlim(a, b)
    ax.axvline(mu, color="#81939E", linewidth=1, linestyle=(0, (3, 3)))
    ax.annotate("平均附近的概率密度较低", xy=(mu, 1 / (math.pi * amplitude)),
                xytext=(mu, .78), ha="center", fontsize=12, color=ink,
                arrowprops={"arrowstyle": "->", "color": muted, "lw": 1})
    ax.text(.025, .93, "密度趋于无穷 ↑", transform=ax.transAxes, color=color, fontsize=11)
    ax.text(.975, .93, "↑ 密度趋于无穷", transform=ax.transAxes, color=color, fontsize=11, ha="right")
    ax.xaxis.set_major_locator(MultipleLocator(.25))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.2f}"))
    ax.grid(axis="y", color="#E3EAF0", linewidth=.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("朔到望的时间间隔（天）", labelpad=12)
    ax.set_ylabel("理论概率密度（每天）", labelpad=12)
    fig.text(.085, .125, "这条曲线是反正弦分布：某段时间的概率等于曲线下对应的面积。端点密度发散，图中纵轴作有限截取。", color=muted, fontsize=10)
    fig.text(.085, .078, "模型只解释整体形状；太阳摄动、多周期项和轨道参数变化未计入，横轴端点不是精确天文极限。", color=muted, fontsize=10)
    fig.text(.085, .033, "同时提供按解析累积分布积分的 1 分钟分箱表；没有抽样噪声。平均参数来源：NASA 月球轨道与食周期资料。", color=muted, fontsize=9)
    for extension in ("png", "svg"):
        fig.savefig(output / f"first_order_arcsine_density.{extension}", dpi=300)
    plt.close(fig)

    result = {
        "model": "first-order fixed-eccentricity elongation model with uniform anomalistic phase at new moon",
        "data_samples_used": 0,
        "mean_synodic_days": SYNODIC_DAYS,
        "mean_anomalistic_days": ANOMALISTIC_DAYS,
        "mean_eccentricity": ECCENTRICITY,
        "mu_days": mu, "amplitude_days": amplitude,
        "support_days": [a, b],
        "model_elongation_radians": "D(t)=w*t+2*e*(sin(phi+n_a*t)-sin(phi)); w=2pi/S, n_a=2pi/P_a",
        "linearized_half_cycle": "T=mu-(4e/w)*sin(n_a*mu/2)*cos(phi+n_a*mu/2), mu=pi/w",
        "density": "1/(pi*sqrt(A^2-(t-mu)^2)) for abs(t-mu)<A, otherwise 0",
        "cdf": "1/2+arcsin((t-mu)/A)/pi inside support, clipped to 0/1 outside",
        "one_minute_probability_sum": float(probabilities.sum()),
        "one_minute_bin_count": len(probabilities),
        "chart_type": "probability density, not per-bin probability; density viewport limited to 1.65/day",
        "assumptions": [
            "Equal weight for anomalistic phases at new moon is an explicit ensemble assumption, not proved here for the real solar system.",
            "Fixed average orbital parameters and first order in eccentricity only.",
            "Solar disturbing-force terms such as evection, solar orbital eccentricity, inclination and apparent-position corrections are omitted.",
            "Apsidal motion is represented only via a fixed mean anomalistic period.",
            "Not fitted to the existing 200-year dataset; endpoints are not physical error-bounded limits."
        ],
        "font": font,
        "sources": ["https://eclipse.gsfc.nasa.gov/LEsaros/LEperiodicity.html",
                    "https://eclipse.gsfc.nasa.gov/help/moonorbit.html"]
    }
    (output / "model.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# 朔到望间隔的简化理论分布\n\n"
        "这是一个明确假设下的解析模型，不使用已有 2,473 个样本，不拟合样本极值，"
        "也不是 DE440 的完整理论概率律。\n\n"
        "假设月相角 D(t)=w t+2e[sin(φ+n_a t)−sinφ]，其中 w=2π/S，"
        "S=29.530589 天，n_a=2π/P_a，P_a=27.554550 天，e=0.0549。"
        "φ 表示朔时的月球平均近点相位，并假设在 [0,2π) 上均匀分布。\n\n"
        "求 D(T)=π，在 μ=π/w 附近保留 e 的一阶项，得到\n\n"
        "T≈μ−(4e/w)sin(n_a μ/2)cos(φ+n_a μ/2)。\n\n"
        "因此 T 是平移缩放的反正弦分布，密度为\n\n"
        "f(t)=1/[π√(A²−(t−μ)²)]，|t−μ|<A。\n\n"
        "相位在时间间隔的极大和极小附近变化时，间隔本身变化缓慢，所以相同宽度的时间格收集到更多相位。"
        "注意这里描述的是“间隔随朔时轨道相位的变化”，不是简单地把月球在远地点走得慢直接当成分布推导。\n\n"
        "图中纵轴是概率密度，每段概率等于曲线下面积。两端的密度趋于无穷但可积，"
        "任意有限分钟格的概率都是有限的，单个精确时长的概率为零。图中纵轴只显示至 1.65/天，端部高密度被截取。\n\n"
        "`analytic_bins_1minute.csv` 则与此前的分钟分箱对应：以整数分钟为边界，"
        "每格概率直接由解析 CDF 相减得到，总和为 1，没有随机抽样。\n\n"
        "太阳摄动、尤其月球出差等周期项，会显著改变这个简单模型的振幅；其他周期还会展宽和改变两端峰形。"
        "因此不能把图中的理论支撑区间当成真实月球的精确范围，也不能据此直接推算农历十五或十六的概率。\n\n"
        "若要求更接近实际的“理论长期分布”，还需指定动力学模型、研究年代，以及如何对轨道相位或朔望周期加权。"
        "在完整模型中可用连续相位积分或确定性数值积分，增加同样 200 年的计算位数不会增加独立朔望事件数。\n\n"
        "复现：在项目根目录运行 `.venv\\Scripts\\python.exe -X utf8 theory.py`。\n\n"
        "平均参数来源：[NASA 月球轨道](https://eclipse.gsfc.nasa.gov/help/moonorbit.html)、"
        "[NASA 食周期](https://eclipse.gsfc.nasa.gov/LEsaros/LEperiodicity.html)。\n",
        encoding="utf-8")
    print(json.dumps({"mu_days": mu, "amplitude_days": amplitude, "support_days": [a,b],
                      "probability_sum": float(probabilities.sum()), "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
