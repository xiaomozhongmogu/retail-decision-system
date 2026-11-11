# Streamlit 导航冒烟（UI-01）

- 2026-11-11，claude-opus-5-5；入口 `app.py`，页面 `src/retail_bi/ui/pages/`，共用 `src/retail_bi/ui/common.py`
- 启动：`.venv/bin/streamlit run app.py --browser.gatherUsageStats false`（本机 8765 端口已被 Anki 占用，冒烟使用 8599）

## 页面入口

| 分组 | 页面 | 路径 | 当前内容 |
|---|---|---|---|
| 数据口径 | 数据口径与质量 | `/data`（默认） | 口径说明，详细页由 UI-02 接入 |
| 经营 | 经营总览 | `/business` | `ads.kpi_monthly` 月度表 |
| 客户 | 生命周期与分群 | `/customers` | 最新 as_of 生命周期分布 |
| 预测 | 复购预测 | `/prediction` | `ads.risk_summary_latest` 与模型能力警示 |
| AI 工作台 | AI 工作台 | `/ai` | 说明 AI 功能未配置凭据 |

每个页面顶部显示数据版本、数据时间范围（2024-01-01 至 2026-11-07）、as_of（2026-11-08，不含），并注明“完全合成数据、模拟历史区间，不是 2026 年实时经营”。

## 实测

| 检查 | 结果 | 证据 |
|---|---|---|
| AppTest 渲染五个页面（有发布版本） | 5/5：无异常，标题与横幅存在，经营/客户/预测页各有一张表 | `evidence/UI-01/smoke_run.log` |
| AppTest 渲染五个页面（发布目录为空） | 5/5：无异常，显示“尚无已发布的数据版本……”，没有表格 | 同上 |
| 真实启动服务 | 健康检查 `ok`，`/`、`/data`、`/business`、`/customers`、`/prediction`、`/ai` 均返回 200 | `evidence/UI-01/server_check.log` |
| 内置浏览器打开 `/business` | 页面文字含横幅与说明，截图显示侧栏五组导航和月度表 | `evidence/UI-01/business_page_browser.jpg` |

前两次真实启动检查打到了占用 8765 端口的 Anki，结果无效，已保留在日志中；换端口后通过。
