# A股短线复盘看板

## 打开看板

在本目录启动一个本地服务：

```bash
.venv/bin/python dashboard/scripts/serve_dashboard.py 8765
```

然后打开：

```text
http://localhost:8765
```

也可以直接运行一键打开脚本：

```bash
dashboard/scripts/open_dashboard.command
```

脚本会自动启动本地服务并打开 `http://127.0.0.1:8765/`。这个链接只在你自己的电脑上可用，适合每天固定打开看盘。

## 数据是否实时

看板不是交易软件那种逐笔实时行情。它展示的是 `dashboard/data/daily.json` 最近一次生成的数据。

- 盘中运行抓数脚本：得到盘中快照。
- 盘后运行抓数脚本：得到盘后复盘。
- 公网版页面会每 60 秒重新读取一次 `data/daily.json`，用于发现云端新快照。
- 使用 `serve_dashboard.py` 启动本地服务时，点击页面“刷新”会先触发 `/api/refresh` 抓新行情，再重新读取 `daily.json`。
- GitHub Actions 会在交易日北京时间约 08:30、11:30、15:30 和 21:00 自动发布。08:30 只刷新新闻、公告与财经日历并保留上一份收盘行情；其余时段抓取完整市场数据，分别用于午盘复盘、收盘快照和晚间完整版复盘。
- 每次云端尝试刷新都会写入 `data/refresh-status.json`，页面顶部会显示最近一次云端尝试时间和成功/失败。

每次生成数据后，页面顶部会显示 `生成 YYYY-MM-DD HH:MM:SS`。

`localhost` 只能自己电脑看。要让别人点击链接也能看到，需要发布到公开静态托管服务。

## 发布到 GitHub Pages

公网看板链接：

```text
https://yuebagui.github.io/a-share-dashboard/
```

公网是纯静态页面，只展示最近一次自动生成并发布的快照。公网可查看：

- 自动复盘报告
- 明日执行表
- A/B/C 候选池
- 预生成技术评分
- 市场盘面、板块资金、风险复盘

公网不可用：

- 从浏览器直接触发整份市场复盘抓数。

公网个股计算器支持输入 6 位股票代码或股票名称，直接读取腾讯实时行情与前复权日 K，在浏览器内完成评分。整份市场复盘抓数仍由 GitHub Actions 定时执行。

项目根目录包含 GitHub Pages 自动刷新配置：

```text
.github/workflows/publish-dashboard.yml
.github/workflows/publish-premarket-news.yml
requirements.txt
```

自动刷新逻辑：

- GitHub Pages 当前从 `main` 分支根目录发布。
- `publish-premarket-news.yml` 在交易日北京时间 08:30 只刷新盘前新闻，不依赖当天涨跌停数据。
- `publish-dashboard.yml` 在交易日北京时间 11:30、15:30 和 21:00 左右运行完整行情复盘。
- 工作流抓取最新数据，写入 `dashboard/data/daily.json`，再运行 `dashboard/scripts/build_static_site.py --out .` 把看板发布文件复制到根目录。
- 如果当次抓数失败，会保留上一份可用数据，避免公网页面空白。
- 也可以在 GitHub Actions 里手动运行 `Refresh A-share review dashboard`，并填写指定交易日；不填写时默认使用最近一个工作日。

如果公网没有自动更新，优先检查：

- GitHub 仓库的 `Actions` 页面是否有 `Refresh A-share review dashboard` 运行记录。
- 仓库 `Settings -> Actions -> General -> Workflow permissions` 是否为 `Read and write permissions`。
- 页面顶部的 `云端尝试` 时间是否变化；如果不变化，说明 GitHub Actions 没有运行或 workflow 没有发布成功。
- 如果 `云端尝试` 变成失败，说明 Actions 跑了，但当次东方财富/同花顺公开接口没有返回可用复盘数据。

更完整的发布检查见：

```text
docs/public-release-checklist.md
```

本地生成根目录发布文件：

```bash
python dashboard/scripts/build_static_site.py --out .
```

## 生成每日数据

```bash
.venv/bin/python dashboard/scripts/fetch_daily.py --date 2026-06-03
```

脚本会写入：

```text
dashboard/data/daily.json
```

页面优先读取 `daily.json`。如果数据为空或接口失败，会自动回退到 `data/sample.json`，确保看板不会空白。

当前真实数据源：

- AkShare `stock_zt_pool_em`: 东方财富涨停池
- AkShare `stock_zt_pool_zbgc_em`: 东方财富炸板池
- AkShare `stock_zt_pool_dtgc_em`: 东方财富跌停池
- AkShare `stock_fund_flow_industry`: 同花顺行业资金流
- AkShare `stock_fund_flow_concept`: 同花顺概念资金流
- AkShare `stock_board_change_em`: 东方财富板块异动，作为概念资金备用源
- AkShare `stock_zh_index_spot_sina`: 新浪指数行情，作为四大指数源
- AkShare `stock_info_global_em`: 东方财富全球财经快讯，作为新闻催化源
- AkShare `stock_info_global_sina`: 新浪全球财经快讯，作为新闻备用源
- AkShare `stock_notice_report`: 东方财富公告大全，作为公告风险/催化源
- AkShare `news_economic_baidu`: 百度财经日历，作为宏观事件源

如果某个源失败，脚本会把原因写入 `daily.json` 的 `meta.errors`，不要把失败源当作 0 数据解读。

## 飞书多维表格复盘

飞书自定义机器人能力变化时，推荐改为“多维表格归档 + 多维表格自动化通知”：

1. 在飞书开放平台创建一个企业自建应用，拿到 `App ID` 和 `App Secret`。
2. 给应用开通多维表格读写权限，并发布/启用应用。
3. 创建一个多维表格，表格字段建议如下：

```text
日期
阶段
生成时间
情绪
情绪分
涨停数
跌停数
炸板率
最高连板
关注板块
强势个股
弱势方向
风险提示
复盘全文
看板数据
```

其中数字类字段可以设置为数字，其余字段用文本/多行文本即可。

4. 在多维表格里创建自动化规则：当新增记录时，通知你本人或指定群。
5. 在本地创建私密配置文件 `dashboard/.feishu.env`：

```text
FEISHU_APP_ID="cli_xxx"
FEISHU_APP_SECRET="xxx"
FEISHU_BITABLE_APP_TOKEN="appxxx"
FEISHU_BITABLE_TABLE_ID="tblxxx"
```

如果你希望飞书归档里出现看板入口，可以配置：

```text
DASHBOARD_URL="http://127.0.0.1:8765/"
```

默认运行脚本会刷新当天行情，并把复盘正文直接输出到终端，适合由 Codex 在对话里转发：

```bash
.venv/bin/python dashboard/scripts/write_feishu_bitable_report.py
```

如需继续写入飞书多维表格，再显式加上 `--feishu`：

```bash
.venv/bin/python dashboard/scripts/write_feishu_bitable_report.py --feishu
```

脚本会先刷新当天行情数据，再生成复盘报告。默认模式不会请求飞书 API；仅在 `--feishu` 模式下才会确保字段存在并向多维表格追加一条记录。`dashboard/.feishu.env` 已加入 `.gitignore`，不要把密钥提交到 GitHub。

旧的自定义机器人脚本仍保留在 `dashboard/scripts/send_feishu_report.py`，但后续自动化建议使用多维表格脚本。

## 看板模块

- Sheet 分区：总览、明日执行、新闻催化、候选股票、市场盘面、板块资金、风险复盘
- 主要指数
- 自动复盘报告：盘前、午间、盘后完整版
- 明日执行表：总仓位、禁买条件、执行纪律和重点标的触发条件
- 新闻催化：东方财富/新浪快讯、东方财富公告、百度财经日历
- 个股打分计算器：本地服务下输入代码后调用短线计算器
- 明日候选股票池：每天21:00扫描沪深主板和创业板全部正常交易股票，排除ST/退市/数据不足，只保留技术评分大于60的全部结果
- 市场情绪指数
- 涨跌停温度
- 涨停票板块/概念归因
- 连板梯队
- 行业资金流入流出
- 概念资金流入流出
- 强于大盘/逆势上涨板块
- 弱于大盘/逆势下跌板块
- 后续关注板块：抗跌、带盘共振、资金强流入综合评分
- 走势分析图：历史接口可用时展示近 24 个交易日趋势；接口不可用时降级为涨幅、超额、资金、评分强弱结构图
- 跌停与负反馈
- 风险雷达
- 明日观察计划

## 个股打分

看板里的“个股打分计算器”支持两种运行方式：

- 公网 GitHub Pages：浏览器直接读取腾讯实时行情和前复权日 K，支持输入代码或股票名称。
- 本地服务：通过 `/api/score` 调用 Python 短线计算器。

启动本地服务后可在页面输入代码，也可以直接请求：

```text
http://127.0.0.1:8765/api/score?code=300750&mode=auto
```

模式支持：

```text
auto / leader / trend / 20cm
```

该接口调用 `skills/short-term-stock-calculator/scripts/calculator.py`，输出评分、买点、止损、止盈、仓位和一票否决项。

## 候选池技术评分

候选池不再只从前一日涨停、跌停或炸板股票中选择。交易日北京时间16:00，独立工作流会把全市场拆成6个分片，分别由6个GitHub Actions运行器并行扫描并合并：

```text
沪深主板：000/001/002/003/600/601/603/605
创业板：300/301
排除：ST、退市、K线不足和抓取失败
入池：自动技术评分 > 60
```

扫描结果保存为 `dashboard/data/universe-candidates.json`，午间和收盘复盘直接复用最近一次完整扫描，避免每个时段重复请求几千只股票。

增强字段包括：

```text
技术总分
MA20
ATR%
量比
60日位置
买点标签
风险标签
一票否决项
```

如果某只股票接口失败或历史 K 线不足，该股票会显示“技术评分失败”或“本次未技术评分”，不会影响其它候选股和整份复盘。

## 明日执行表

执行表会把市场温度、候选池和技术评分翻译成次日动作清单：

```text
总仓位上限
单票仓位上限
市场策略姿态
禁止交易条件
开仓/加仓/止损纪律
重点标的执行卡片
```

每张执行卡片包含观察级别、动作、触发条件、止损条件、时间窗口、仓位和技术否决项。执行表只给条件式计划，不给无条件买入指令。
