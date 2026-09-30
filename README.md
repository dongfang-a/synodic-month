# 高精度朔望时刻程序

已实现并实际计算 **1926-09-29 至 2126-09-29** 的 200 年天文基础数据，并新增基于 **2,473 个区间内望事件**的经验概率分布图。基础数据文件不含农历日期；新增分析按东八区和朔日为初一的规则计算农历日序。

“完全准确”没有可承诺的绝对意义。本程序采用明确的天文定义、JPL 数值历表、可复核的求解误差和独立对照；不把输出的小数位数当作天文准确度。

## 已生成的结果

默认区间是 **TT 公历日期、左闭右开**：`[1926-09-29 00:00, 2126-09-29 00:00)`。
该默认值固定以本项目需求日期 2026-09-29 为中心，运行日期变化不会自动改变样本范围。

| 文件 | 用途 |
| --- | --- |
| `output/1926-2126/events.csv` | 区间内 2,474 次朔、2,473 次望，共 4,947 个事件 |
| `output/1926-2126/lunations.csv` | 2,474 个朔望月的朔、望、下一次朔和实际时长 |
| `output/1926-2126/results.json` | 上述两张表和计算元数据 |
| `output/1926-2126/manifest.json` | 时间尺度、算法、软件版本、历表/闰秒/输出文件 SHA-256 |
| `output/1926-2126/validation.json` | 全量结构检查和独立数据对照报告 |

朔望月记录按**本次朔在区间内**选择。因此最后一行的望或下一次朔可能在区间外，相关字段已明确标注；事件表只包含区间内的事件。两张表的望数量不同是这个选择规则的结果。

本次实测完整批处理约 21 秒（不含首次下载，速度随机器变化）。月长范围为约 **29.274351—29.829771 TT 日**。1 TT 日为 86,400 秒。

## 运行

当前目录的虚拟环境、历表和闰秒表已经准备好。PowerShell 中运行：

```powershell
# 查看帮助
.\run.ps1

# 重算默认 200 年，覆盖已有本程序输出
.\run.ps1 calculate --overwrite

# 计算另一个区间，保留独立输出
.\run.ps1 calculate --start 2000-01-01 --end 2100-01-01 --out output/2000-2100

# 现代日期可用 UTC 边界；同时输出上弦、下弦
.\run.ps1 calculate --start 2024-01-01 --end 2025-01-01 --boundary-scale utc --all-phases --out output/2024 --overwrite
```

如果本机脚本策略阻止 `.ps1`，直接运行，不需要修改系统策略：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m synodic calculate --overwrite
```

新环境需要 **Python 3.12 或更新版本**：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -X utf8 -m synodic prepare
.\.venv\Scripts\python.exe -X utf8 -m synodic calculate
```

`prepare` 从 NASA 下载约 32 MB 的 DE440s，并从 IANA 下载 IERS 闰秒数据。已有文件默认保留；计算与测试阶段完全离线，不自动更换数据版本。

```powershell
# 显式刷新闰秒数据，然后另存或重算结果
.\run.ps1 prepare --refresh-leaps
```

## 计算定义与方法

使用地心观测的日、月**视黄经差**，朔为 0°，望为 180°；上弦、下弦分别为 90°、270°。这与 [USNO 月相定义](https://aa.usno.navy.mil/faq/moon_phases)一致。它不是日月角距离最小、月面照明比例最大或月食最甚时刻。

1. 读取 JPL DE440s 的日、地、月位置；这个短时间跨度文件覆盖 1849-12-25 至 2150-01-21，可覆盖本次 200 年及两端补算。
2. 用 Skyfield `observe().apparent()` 处理光行时、光行差、引力偏折，再转换到日期黄道坐标。采用 Skyfield 默认的完整 IAU 2000A 章动模型，不使用简化月相级数或平均月长累加。
3. 在均匀的 TT 时间上以两天步长定位相位跨越，再用双分量儒略日进行二分求根，默认最终包围区间宽度不超过 **0.001 秒**。
4. 按 366 天分块；块边界重叠并去重，区间两端各补算 32 天，用于完整配对。
5. 月长由相邻两次朔的 TT 时刻直接相减。原始 TT/TDB 双分量时间保留，避免把单个大儒略日浮点数当作全部精度。

历表不足时明确报错，不外推、不偷偷切换到低精度算法。需要更大范围时可下载完整 `de440.bsp`，通过 `--kernel 路径` 指定。

## 时间字段：后续统计必须保留这个区别

| 字段 | 含义 |
| --- | --- |
| `tt` | 核心天文计算时间，字符串保留毫秒；**不是 UTC** |
| `tt_jd_whole` + `tt_jd_fraction` | 完整 TT 儒略日的两个分量，重算/比较时优先使用 |
| `tdb_jd_whole` + `tdb_jd_fraction` | 对应 TDB 儒略日，便于与历表工具交叉比较 |
| `ut1_estimate` | 地球自转时间估计，使用 `UT1 = TT - ΔT`；历史和未来都依赖模型 |
| `delta_t_seconds` | 本次换算使用的 ΔT |
| `utc` | 仅在 1972 年起、且闰秒表有效期内填写的 UTC |
| `local_fixed_offset` | 有效 UTC 加固定偏移；默认 +08:00，可用 `--offset-hours` 修改 |
| `utc_provisional` | 超过闰秒表有效期的条件性投影，**假设最后一个 TAI−UTC 值不再改变** |
| `local_fixed_offset_provisional` | 上述条件性投影加固定偏移 |
| `utc_status` | 说明该行采用有效闰秒表、未来条件假设，还是不提供早期 UTC |
| `preceding_new_tt` | 事件所属周期的前一次朔；朔事件取自身 |
| `numerical_bracket_seconds` | 数值求解区间宽度，**不是实际天文误差** |
| `longitude_residual_arcseconds` | 求解后的黄经差残差 |

所有日期采用延伸公历。TT、UT1 字符串没有 `Z`，只有 UTC 字符串带 `Z`。CSV 使用带 BOM 的 UTF-8，JSON 中缺失值为 `null`，CSV 中为空。

1972 年以前的 UTC 涉及不同历史定义，本版本明确不实现这部分换算；早期只提供 TT 与 UT1 估计。未来实际 UTC、闰秒和计时制度不可由天文历表独自预知，所以条件性投影不会填入正式 `utc` 字段。

附带闰秒表更新于 2026-07-06，文件到期日为 **2027-06-28**；程序每次读取文件本身的有效期，不硬编码该日期。UT1 则使用固定 Skyfield 版本自带的 IERS 数据与历史/未来 ΔT 模型，文件摘要写入 manifest。未来 UT1 也不保证精确。

默认 +08:00 是方便后续中文历日研究的固定偏移，**没有实现历史中国时区、夏令时或未来法定时间规则**。用户所在系统时区不会悄悄影响结果。若事件恰好落在闰秒，UTC 保留 `:60`，受 Python datetime 限制，本地字符串留空。

`--boundary-scale tt` 是默认输入范围；也可选择 `ut1`。只有整个边界范围位于闰秒表有效期内时才允许 `utc`，避免对 2126 年输入一个貌似已经确定的 UTC 范围。

## 精度证据与已知限制

已运行 **22 项测试**，覆盖角度 0° 跨越、求根残差、不同扫描步长与分块、精度收敛、空区间、月末补算、闰秒、日期进位、历表边界、输出完整性、重复写入保护、农历日序与统计分箱。

另外验证了完整 200 年输出的事件顺序、朔望交替、周期连续性、月长范围、时间字段和文件摘要。

独立交叉验证包含：

- **USNO**：1926、1980、2000、2024、2100 年共 248 个四相事件，数量和相位一致。各年相对公布分钟值的最大差约为 34.032、29.653、30.567、39.705、50.891 秒。2024 年差异超过单纯分钟舍入范围，其具体来源尚未确认；此项只能作为分钟级对照。
- **JPL Horizons**：1926、1980、2000、2024、2100、2126 年的 24 个抽样时刻，从官方服务独立获得日月视黄经。最大相位残差为 **0.007920 角秒**，用局部月相角速度折算的最大时间差约 **0.016725 秒**。Horizons 原始响应采用 DE441 与 IAU76/80，本程序采用 DE440s 与 Skyfield 的现代模型；因此这是跨模型的样本一致性证据，不是整个 200 年相对真实宇宙的误差上限。

原始官方响应保存在 `tests/fixtures/`，常规测试不联网，也不把本程序的输出伪装成独立参考数据。数值求根实际最大包围区间约 0.000642 秒，这与历表精度、相对论/坐标模型及 ΔT 不确定性是不同概念。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
.\.venv\Scripts\python.exe -X utf8 validate.py
```

若确实需要重新向 Horizons 获取独立参考快照，可显式执行 `python tests/fetch_horizons.py`；一般不需要。

## 为后续概率研究保留的条件

本程序输出“本次朔—望—下一次朔”，并保留跨日所需的时间尺度和固定偏移信息。
分析时需要明确采用的历日规则、时区、历史或未来时间换算假设、样本边界，以及对接近午夜事件的误差处理。不能简单把朔到望的时长取整就认定农历十五或十六；新增分析使用朔、望的东八区公历日期差加一确定日序。

## 已完成的分布图分析

运行 `.venv\Scripts\python.exe -X utf8 analyze.py` 可直接复现，不重新计算天文历表。
新环境需安装 `pip install -e ".[analysis]"` 并提供微软雅黑或 Noto Sans CJK SC 字体。

输出目录：`output/1926-2126/distributions/`。

- `01_new_to_full_1minute.png/svg`：朔到望的 TT 时间间隔，bin = 1 分钟。
- `02_full_moon_lunar_day_1hour.png/svg`：东八区望的农历日序和钟表时刻，bin = 1 小时。
- 各图分箱 CSV、逐样本 CSV、农历日总计 CSV 和统计说明一并保存在该目录。

两图均使用望落在原计算区间内的 2,473 个周期，排除月表最后一行在 2126-10-01 的望。
所有概率统一为每格计数除以 2,473。第二图只裁去两端无样本的小时格，显示十四 22:00 至十七 14:00（右端不含）；中间时间轴连续。
东八区按固定 +8 处理：1972 年前为 UT1 估计加八小时，有效期内为 UTC 加八小时，未来为已有条件性 UTC 投影加八小时。
这些是本次 200 年样本的经验频率，不是所有年代的理论概率或绝对不可能区间。

## Git 仓库中的内容

仓库保存源码、测试参考快照、闰秒表以及 `output/` 下的已计算数据和图表，便于直接查看及复现。
`.venv/`、Python 缓存和可重新下载的 `data/*.bsp` 历表不纳入版本控制。
克隆后按上面的新环境安装步骤运行 `python -m synodic prepare` 即可取得历表；
若还要重新绘图，安装 `pip install -e ".[test,analysis]"`。
数据快照通过 `.gitattributes` 保留原始换行字节，避免跨平台检出改变已记录的 SHA-256。

## 资料来源

- [JPL DE440/DE441 技术论文说明](https://ssd.jpl.nasa.gov/doc/de440_de441.html)
- [NASA NAIF 官方历表目录](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/)
- [Skyfield 月相接口与定义](https://rhodesmill.org/skyfield/api-almanac.html)
- [Skyfield 时间尺度说明](https://rhodesmill.org/skyfield/time.html)
- [IANA 发布的 IERS 闰秒表](https://data.iana.org/time-zones/data/leap-seconds.list)
- [USNO 月相 API](https://aa.usno.navy.mil/data/api)
- [JPL Horizons 手册，观测量 31](https://ssd.jpl.nasa.gov/horizons/manual.html)
