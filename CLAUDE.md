# CLAUDE.md — Market Calendar

美盘事件日历（纯静态网页，GitHub Pages）。标记 非农 / CPI / FOMC / CME(ES/NQ 期货) 假期。
线上：https://jcl1021-svg.github.io/market-calendar/

## 本项目工作须知

- **`data.json` 是自动生成的，别手改**。要改数据一律跑 `python3 scripts/fetch_data.py` 重新生成。
- **`.env` 绝不提交**（含 `FRED_API_KEY`，已 gitignore）。网页运行时不需要 key，只在本地生成数据时用。
- 数据源：
  - FOMC ← 美联储官网页解析；
  - 非农 / CPI ← FRED API（需 `.env` 里的 `FRED_API_KEY`，记录 BLS 实际发布日）；
  - CME 假期 ← `fetch_data.py` 里手工核准的 `CME_HOLIDAYS` 显式表。
- **CME 官网封 bot**（curl / WebFetch / 无头浏览器都被 403 / 协议层拒绝，抓不到）。所以 CME 假期用手工表 + 照搬官方的镜像站交叉核对；`exchange_calendars` 库不可靠（漏过 Juneteenth），别依赖。
- 数据准确性靠**每年人工核对一次**：用 BLS 官方存档 URL `empsit_MMDDYYYY.htm` / `cpi_MMDDYYYY.htm`（文件名即实际发布日）逐条比对。不做自动外部核对（会误报）。
- 脚本内 `sanity_check()` 离线体检（数量 非农/CPI 各12、FOMC 8；不落周末；无重复；年份不越界），生成时自动跑。
- 网页过期横幅：`data.json` 最大年份 < 当前年时，页面顶部提醒重新生成。

## 一年更新一次数据

1. 在 `fetch_data.py` 的 `CME_HOLIDAYS` 补下一年假期表（对 CME 官网核对）；
2. `python3 scripts/fetch_data.py`（离线体检通过才写 `data.json`）；
3. `git add . && git commit && git push`（Pages 自动更新）。

设计文档：`docs/superpowers/specs/2026-07-02-market-calendar-design.md`
