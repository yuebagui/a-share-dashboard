# 公网发布检查清单

更新日期：2026-06-23

## GitHub Pages

- 仓库 Settings -> Pages 选择从 `main` 分支根目录发布。
- 仓库 Settings -> Actions -> General -> Workflow permissions 选择 `Read and write permissions`。
- 根目录保留 `.nojekyll`，避免 GitHub Pages 走 Jekyll 处理。
- 公网入口：`https://yuebagui.github.io/a-share-dashboard/`。

## 自动刷新

工作流：`.github/workflows/publish-dashboard.yml`

定时任务：

- 北京时间 11:30：午间复盘。
- 北京时间 15:30：收盘快照。
- 北京时间 21:00：盘后完整版。

每次运行应更新：

- `dashboard/data/daily.json`
- `dashboard/data/refresh-status.json`
- `data/daily.json`
- `data/refresh-status.json`
- 根目录 `index.html`、`app.js`、`styles.css`

## 公网降级策略

公网是纯静态页面：

- 可以展示最近一次自动生成的复盘、执行表、候选池和预生成技术评分。
- 可以每 60 秒重新读取已发布的 `data/daily.json`。
- 不能实时调用 `/api/score`。
- 不能从浏览器触发真实抓数。

本地服务版：

- 支持 `/api/refresh` 实时抓取最新数据。
- 支持 `/api/score?code=300750&mode=auto` 实时个股打分。

## 发布前自检

```bash
/Users/kingkevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check dashboard/app.js
/Users/kingkevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -c 'import json; json.load(open("dashboard/data/daily.json", encoding="utf-8")); json.load(open("data/daily.json", encoding="utf-8")); print("json ok")'
python3 dashboard/scripts/build_static_site.py --out .
```

## 页面合规

公网页面底部必须固定显示免责声明：

```text
本页面内容仅为个人/团队交易复盘、数据整理与策略研究记录，不构成任何投资建议、收益承诺或买卖依据。市场有风险，交易需独立判断并自行承担风险。
```
