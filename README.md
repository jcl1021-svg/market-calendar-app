# Market Calendar · 美盘事件日历

深色月历网页,标记 **非农 (NFP) / CPI / FOMC / CME(ES/NQ 期货)假期**。纯静态,托管在 GitHub Pages。

## 数据源(权威)

| 事件 | 来源 |
|------|------|
| FOMC | 美联储官网 FOMC 日程 |
| 非农 / CPI | FRED API(圣路易斯联储,记录 BLS 实际发布日) |
| CME 假期 | 逐条核对的显式表(`scripts/fetch_data.py` 内 `CME_HOLIDAYS`) |

数据是**权威快照**,写在 `data.json`,约**一年更新一次**(日期年初一次性公布、极少变)。

## 本地预览

```bash
python3 -m http.server 8765
# 浏览器打开 http://localhost:8765/index.html
```
> 注:必须经静态服务器,直接 `file://` 打开会因 CORS 无法读取 `data.json`。

## 一年更新一次数据

1. 在 `scripts/fetch_data.py` 的 `CME_HOLIDAYS` 里补上**新一年**的假期表(对着 CME 官网核对);
2. 本地建 `.env` 写入 FRED key:`FRED_API_KEY=你的key`(此文件已被 `.gitignore` 排除,不会提交);
3. 运行:
   ```bash
   YEARS=2027 python3 scripts/fetch_data.py     # 或不带 YEARS,默认当前年
   ```
   脚本会跑**离线体检**(数量/周末/重复/年份),通过后重写 `data.json`;
4. `git commit` 并 `git push`,GitHub Pages 自动更新。

> 免费 FRED key 申请:https://fred.stlouisfed.org/docs/api/api_key.html

## 过期提醒

打开网页时,若 `data.json` 的最大年份 < 当前年份,页面顶部会弹黄条提醒重新生成。

## 结构

```
index.html / style.css / app.js   # 网页
data.json                         # 权威数据(自动生成)
assets/fonts/                     # 自带 Inter 字体(不依赖外网)
scripts/fetch_data.py             # 生成数据 + 离线体检
docs/superpowers/specs/           # 设计文档
```
