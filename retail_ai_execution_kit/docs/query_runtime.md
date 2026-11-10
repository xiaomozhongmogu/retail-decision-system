# 只读查询运行时（DW-10）

- 版本：v1，2026-11-10，claude-opus-5-5
- 代码：`src/retail_bi/warehouse/release.py`（发布、回滚）、`src/retail_bi/warehouse/runtime.py`（应用和 AI 的唯一查询入口）
- 当前发布登记：`reports/warehouse/published_snapshot.json`

## 1. 谁写、谁读

| 角色 | 进程 | 读写范围 |
|---|---|---|
| 离线构建 | `pipeline.py build`（命令行，单写者） | 只写 `warehouse/builds/`，成功后原子更新 `builds/latest.json` |
| 发布 | `release.py publish`（命令行） | 把最新构建复制到 `warehouse/releases/<版本>.duckdb`（文件权限 0444），再原子替换 `releases/current.json` |
| 应用与 AI | Streamlit 进程、AI 工具 | 只通过 `runtime.open_current()` / `runtime.query_view()` 以 `read_only=True` 打开 `current.json` 指向的发布文件 |

构建和应用是两个独立的生命周期：应用持有只读连接时，离线构建照常运行，已发布文件不变（DW-10 实测）。

## 2. 查询规则

- 只能查询发布时登记在 `meta.allowed_view` 中的 ADS 视图：`ads.kpi_daily`、`ads.kpi_monthly`、`ads.sales_month_category_region`、`ads.cohort_retention`、`ads.lifecycle_mix_weekly`、`ads.repurchase_rate_weekly`，以及有评分时的 `ads.risk_summary_latest`（ML-11，只有平均水平）。客户级的 `ads.model_scores` 和 `ads.customer_profile_latest` 不在清单内。
- `query_view` 只接受视图名、列名（小写标识符）、等值条件和行数上限（最多 5,000 行），由程序拼成一条 SELECT；条件值走参数绑定。其他表返回 `unsupported`，非法列名返回 `invalid_argument`，没有结果返回 `empty`。
- 结果带 `dataset_version` 和 `mode: live`，与 `contracts/interfaces.md` 的结果信封一致。

## 3. 缓存失效

- 查询结果按（发布版本、SQL、参数）缓存。发布新版本后版本号变化，旧缓存不会再被命中（实测：新版本第一次查询为未命中）。
- 打开发布文件前核对其 SHA-256 与 `current.json` 一致；文件大小或修改时间不变时复用核对结果。哈希不符时拒绝打开（`ReleaseError`）。

## 4. 文件身份与恢复

- `current.json` 记录版本、文件名、SHA-256、字节数、来源构建、发布时间和上一版本；`history.json` 记录每个版本的上一版本。
- 发布中断（复制失败、校验不符、指针替换前出错）时，`current.json` 仍指向原版本，临时复制文件被删除，读取不受影响（实测）。
- 回滚：

```bash
.venv/bin/python src/retail_bi/warehouse/release.py rollback
```

- 发布文件丢失或损坏时，从原始 ZIP 重建并重新发布：

```bash
.venv/bin/python src/retail_bi/pipeline.py build --force && .venv/bin/python src/retail_bi/warehouse/release.py publish
```

  DuckDB 文件的字节在两次构建之间可能不同，因此重建后的版本以内容检查（DW-09 对账）为准，并记录新的 SHA-256。
