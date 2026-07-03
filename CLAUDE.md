# CLAUDE.md — Market Calendar

美盘事件日历（纯静态网页，GitHub Pages）。标记 非农 / CPI / FOMC / CME(ES/NQ 期货) 假期。
线上：https://jcl1021-svg.github.io/market-calendar-app/

## 本项目工作须知

- **`data.json` 是自动生成的，别手改**。要改数据一律跑 `python3 scripts/fetch_data.py` 重新生成。
- **`.env` 绝不提交**（含 `FRED_API_KEY`，已 gitignore）。网页运行时不需要 key，只在本地生成数据时用。
- 数据源：
  - FOMC ← 美联储官网页解析；
  - 非农 / CPI ← FRED API（需 `.env` 里的 `FRED_API_KEY`，记录 BLS 实际发布日）；
  - CME 假期 ← `fetch_data.py` 里手工核准的 `CME_HOLIDAYS` 显式表。
- **CME 官网封 bot**（curl / WebFetch / 无头浏览器都被 403 / 协议层拒绝，抓不到）。用户也不自行核对，所以下一年 CME 假期表由 Claude 按下面方法确定，务必照做：
  1. **取 ≥3 个独立、照搬 CME 官方的期货假期表**（crosstrade / discounttrading / metrotrade / prop 教程等）互相交叉比对；
  2. **再按 CME 股指固定规则自算一份当标尺**：全休 = 元旦 / 耶稣受难日 / 圣诞（三天）；其余 = 早收（MLK、总统日、阵亡将士日、Juneteenth、独立日相关、劳动节、感恩节、黑五、平安夜）；观察日按美国联邦规则（周六→前周五、周日→次周一）；
  3. **三方一致才录入** `CME_HOLIDAYS`；哪天对不上，去搜索引擎找 CME 官方 PDF 公告（站点抓不了但能被索引到）锁死，别猜；
  4. **绝不只信单一网站或某个库**——`exchange_calendars` 漏过 Juneteenth，就是靠多源交叉抓出来的。
- 数据准确性靠**每年人工核对一次**：用 BLS 官方存档 URL `empsit_MMDDYYYY.htm` / `cpi_MMDDYYYY.htm`（文件名即实际发布日）逐条比对。不做自动外部核对（会误报）。
- 脚本内 `sanity_check()` 离线体检（数量 非农/CPI 各12、FOMC 8；不落周末；无重复；年份不越界），生成时自动跑。
- 网页过期横幅：`data.json` 最大年份 < 当前年时，页面顶部提醒重新生成。

## 一年更新一次数据

1. 在 `fetch_data.py` 的 `CME_HOLIDAYS` 补下一年假期表（对 CME 官网核对）；
2. `python3 scripts/fetch_data.py`（离线体检通过才写 `data.json`）；
3. `git add . && git commit && git push`（Pages 自动更新）。

> 数据一更新，邮件提醒会自动跟着新数据走，无需额外操作。

## 邮件提醒（每日自动）

- `.github/workflows/reminder.yml` 每天**北京时间 12:00**（cron `0 4 * * *` = 04:00 UTC）跑 `scripts/send_reminder.py`：读 `data.json`，**事件前一天**把提醒发到主 Gmail；无事件不发。覆盖全部事件（非农 / CPI / FOMC / 假期）。
- 发信走 **Gmail SMTP**，用**发信小号**（非主号，泄露也不碰主邮箱）。GitHub 仓库 3 个 Secret：`GMAIL_ADDRESS`（小号）、`GMAIL_APP_PASSWORD`（小号应用专用密码，脚本自动去空格）、`MAIL_TO`（收件主邮箱）。**这些只在 GitHub Secret 里，绝不进代码/`.env` 不提交。**
- **keepalive 用内联 git 空提交**（≥50 天没提交才空提交一次）防 GitHub 60 天自动禁用定时任务。**⚠️ 别用第三方 keepalive action `gautamkrishnar/keepalive-workflow`——已被 GitHub 因 TOS 永久封禁（`Repository access blocked`）。**
- 本地/手动测试：`python3 scripts/send_reminder.py --dry-run --date YYYY-MM-DD`（只打印不发）；或 GitHub `Actions → Daily market reminder → Run workflow` 填 `date` 真发一封。测试逻辑见 `tests/test_send_reminder.py`（stdlib unittest，`python3 -m unittest discover -s tests`）。

设计文档：`docs/superpowers/specs/2026-07-02-market-calendar-design.md`、`docs/superpowers/specs/2026-07-03-email-reminders-design.md`
