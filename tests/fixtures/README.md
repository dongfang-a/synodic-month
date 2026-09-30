# 独立对照数据

`usno-YEAR.json` 下载自美国海军天文台的原始 JSON API：

`https://aa.usno.navy.mil/api/moon/phases/year?year=YEAR`

年份为 1926、1980、2000、2024、2100。API 版本和实际时刻保留在 JSON 内。
该服务输出至分钟、标注 Universal Time；这是事件完整性与分钟级交叉检查，不能验证毫秒级绝对准确度。
1972 年以前以及远期对照采用本程序 UT1 估计。2100 年允许不同 ΔT 预测带来的更大差异。
现代年份 UTC 和 UT1 的亚秒差别小于此处对照容限。

接口说明：https://aa.usno.navy.mil/data/api

测试不请求网络，不从待测程序生成参考时刻。

## JPL Horizons 视黄经校验

`horizons-moon.json`、`horizons-sun.json` 是 Horizons 原始响应；`horizons-samples.json`
保存 1926、1980、2000、2024、2100、2126 六个年份的共 24 个查询时刻和对应视黄经。
查询时刻由本程序选定，视黄经数值来自独立的 JPL Horizons 服务。
地心 `500@399`，时间 `TT`，观测量 `31`，光行时、光行差、光偏折均包含。
原始响应注明 DE441 和 IAU76/80；本程序为 DE440s 和 Skyfield 的现代岁差章动模型，
因此不是逐位相同的算法校验。测试允许 0.02 角秒的黄经差，不能作为观测真值误差上限。

`python tests/fetch_horizons.py` 可显式联网重新采集；一般验证不需要执行。

USNO 的 2024 年分钟表存在约 40 秒的最大差异，超过单纯四舍五入的 30 秒范围，
具体来源尚未确认。将其作为一分钟级交叉检查，不能用它证明亚秒绝对准确度；
更细的模型交叉校验见 Horizons 快照。
