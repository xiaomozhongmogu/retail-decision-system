"""Build midterm charts from the project's structured result files (no hand-typed numbers).

Usage: python charts.py <project_root> <out_dir>
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

root = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

font_manager.fontManager.addfont("/System/Library/Fonts/Hiragino Sans GB.ttc")
plt.rcParams["font.family"] = "Hiragino Sans GB"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

BLUE, ORANGE, GREY, GREEN, RED = "#2563EB", "#EA580C", "#9CA3AF", "#16A34A", "#DC2626"
DPI = 200


def load(p):
    return json.loads((root / p).read_text(encoding="utf-8"))


eda = load("reports/analysis/eda_initial.json")
clus = load("reports/model/cluster_metrics.json")
test = load("reports/model/test_metrics.json")
used = {}

# 1. monthly trend (complete months only)
months = [m for m in eda["monthly"] if m["month"] != "2026-11"]
x = list(range(len(months)))
fig, ax1 = plt.subplots(figsize=(10, 4))
ax1.bar(x, [m["merch_usd"] / 1000 for m in months], color=BLUE, alpha=0.8, label="商品金额（千 USD）")
ax1.set_ylabel("商品金额（千 USD）")
ax2 = ax1.twinx()
ax2.plot(x, [m["valid_orders"] for m in months], color=ORANGE, marker="o", ms=3, label="有效订单")
ax2.set_ylabel("有效订单（单）")
ax2.spines["right"].set_visible(True)
ax1.set_xticks(x[::3])
ax1.set_xticklabels([m["month"] for m in months][::3], rotation=0, fontsize=8)
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)
ax1.set_title("2024-01 至 2026-10 月度有效订单与商品金额（2026-11 不完整，未画）", fontsize=11)
fig.tight_layout()
fig.savefig(out / "fig_monthly.png", dpi=DPI)
plt.close(fig)
used["fig_monthly"] = "reports/analysis/eda_initial.json#monthly"

# 2. lifecycle mix at latest as_of (read from release ADS view, passed via json side file)
life = json.loads((out / "lifecycle_latest.json").read_text(encoding="utf-8"))
names = {"new": "新客", "active": "活跃", "at_risk": "沉默预警", "dormant": "沉睡"}
order = ["new", "active", "at_risk", "dormant"]
vals = [life["counts"][k] for k in order]
fig, ax = plt.subplots(figsize=(6, 3.4))
bars = ax.bar([names[k] for k in order], vals, color=[GREEN, BLUE, ORANGE, GREY])
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 20, f"{v:,}", ha="center", fontsize=9)
ax.set_ylabel("客户数")
ax.set_title(f"生命周期状态分布（as_of {life['as_of']}）", fontsize=11)
fig.tight_layout()
fig.savefig(out / "fig_lifecycle.png", dpi=DPI)
plt.close(fig)
used["fig_lifecycle"] = "warehouse release ads.lifecycle_mix_weekly (latest as_of)"

# 3. RFM rule segments: customer share vs M share
seg = clus["rule_segments"]["apply_as_of_profile"]
labels = [s["segment"].split("（")[0] for s in seg]
cs = [s["share"] * 100 for s in seg]
ms = [s.get("m_total_share", s.get("m_share", 0)) * 100 for s in seg]
fig, ax = plt.subplots(figsize=(7, 3.6))
w = 0.38
xi = range(len(seg))
ax.bar([i - w / 2 for i in xi], cs, w, color=GREY, label="客户占比")
ax.bar([i + w / 2 for i in xi], ms, w, color=BLUE, label="近 90 天金额占比")
for i in xi:
    ax.text(i - w / 2, cs[i] + 0.8, f"{cs[i]:.1f}%", ha="center", fontsize=8)
    ax.text(i + w / 2, ms[i] + 0.8, f"{ms[i]:.1f}%", ha="center", fontsize=8)
ax.set_xticks(list(xi))
ax.set_xticklabels(labels)
ax.set_ylabel("%")
ax.legend(frameon=False)
ax.set_title(f"RFM 规则分群：客户占比与金额占比（as_of {clus['definition']['as_of_apply'][:10]}，{clus['rows']['apply']} 人）", fontsize=10)
fig.tight_layout()
fig.savefig(out / "fig_rfm.png", dpi=DPI)
plt.close(fig)
used["fig_rfm"] = "reports/model/cluster_metrics.json#rule_segments.apply_as_of_profile"

# 4. test ROC-AUC with CI + weekly lift
sc = test["scores"]
items = [("p_model", "逻辑回归"), ("rule_frequency_90d", "规则：90天订单数"), ("rule_recency", "规则：最近购买")]
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6))
for i, (k, n) in enumerate(items):
    v = sc[k]["roc_auc"]
    lo, hi = sc[k]["roc_auc_95ci"]
    a.errorbar(i, v, yerr=[[v - lo], [hi - v]], fmt="o", color=BLUE, capsize=6)
    a.text(i + 0.08, v, f"{v:.3f}", fontsize=9, va="center")
a.axhline(0.5, color=RED, ls="--", lw=1, label="随机 = 0.5")
a.set_xticks(range(3))
a.set_xticklabels([n for _, n in items], fontsize=9)
a.set_ylim(0.44, 0.58)
a.set_xlim(-0.4, 2.6)
a.set_title("测试集 ROC-AUC 与 95% 客户分块区间", fontsize=10)
a.legend(frameon=False, loc="upper right")
lifts = [sc[k]["weekly_lift@10%"] for k, _ in items]
bars = b.bar([n for _, n in items], lifts, color=[BLUE, GREY, GREY])
for bb, v in zip(bars, lifts):
    b.text(bb.get_x() + bb.get_width() / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
b.axhline(1.0, color=RED, ls="--", lw=1, label="随机 = 1.0")
b.set_ylim(0, 1.3)
b.set_title("周内 Lift@10%（每周取前 10% 客户）", fontsize=10)
b.tick_params(axis="x", labelsize=9)
b.legend(frameon=False, loc="upper right")
fig.suptitle(f"时间外测试：{test['test_set']['rows']:,} 行 / {test['test_set']['customers']:,} 名客户，正例比例 {test['test_set']['positive_rate']*100:.1f}%", fontsize=11)
fig.tight_layout()
fig.savefig(out / "fig_test.png", dpi=DPI)
plt.close(fig)
used["fig_test"] = "reports/model/test_metrics.json#scores"

# 5. calibration
rel = sc["p_model"]["reliability"]
fig, ax = plt.subplots(figsize=(5.2, 3.6))
ax.plot([r["mean_pred"] for r in rel], [r["observed"] for r in rel], "o-", color=BLUE, label="十分位组")
lim = [0.04, 0.095]
ax.plot(lim, lim, "--", color=GREY, label="完美校准")
ax.set_xlim(lim)
ax.set_ylim(lim)
ax.set_xlabel("平均预测概率")
ax.set_ylabel("实际复购比例")
ax.set_title(f"校准：ECE = {sc['p_model']['ece']}", fontsize=10)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(out / "fig_calibration.png", dpi=DPI)
plt.close(fig)
used["fig_calibration"] = "reports/model/test_metrics.json#scores.p_model.reliability"

# 6. architecture / data flow diagram
fig, ax = plt.subplots(figsize=(11, 5.2))
ax.set_xlim(0, 110)
ax.set_ylim(0, 52)
ax.axis("off")


def box(x, y, w, h, text, fc="#EFF6FF", ec=BLUE, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color="#374151", lw=1.1))


ax.text(28, 50, "离线批处理（命令行，可重跑）", ha="center", fontsize=10, weight="bold")
ax.text(84, 50, "在线只读（Streamlit 应用）", ha="center", fontsize=10, weight="bold")
col = [("原始 ZIP（合成交易包）\n核对 SHA-256", "#F3F4F6", GREY),
       ("导入 → 清洗 → 交易规则\n质量门槛 10/10", "#F3F4F6", GREY),
       ("ODS  原样保留＋批次元数据", "#EFF6FF", BLUE),
       ("DWD  星型：订单/明细/支付/履约事实\n客户·商品·日期·地区·卖家维度", "#EFF6FF", BLUE),
       ("DWS  日汇总；客户×as_of 时点快照", "#EFF6FF", BLUE),
       ("ADS  指标语义视图（白名单）", "#EFF6FF", BLUE)]
y = 42
for t, fc, ec in col:
    box(4, y, 40, 5.2, t, fc, ec)
    if y < 42:
        arrow(24, y + 7.6, 24, y + 5.6)
    y -= 7.6
box(48, 26, 14, 9, "特征/标签\n→ 训练 → 评分\n（逻辑回归 v1）", "#FFF7ED", ORANGE, 8.5)
box(48, 38, 14, 8, "知识库 kb-v1\n指标/数据字典\n模型卡/运营规则", "#FFF7ED", ORANGE, 8.5)
arrow(44, 13.5, 48, 30)
box(66, 12, 14, 14, "只读发布\nwh-<版本>.duckdb\n原子切换\n可回滚", "#ECFDF5", GREEN, 9)
arrow(44, 5.6, 66, 15)
arrow(62, 30, 66, 22)
box(84, 38, 23, 8, "五类页面：数据口径｜经营总览\n客户生命周期｜复购预测｜AI 工作台", "#EFF6FF", BLUE, 8.5)
box(84, 22, 23, 13, "AI 工具层\n查询助手：意图→受限 SQL→只读执行\n周报：SQL 事实→LLM→数字校验\n挽回 Agent：画像→政策→预算→草稿", "#FDF2F8", "#DB2777", 8)
box(84, 6, 23, 11, "LLM 适配器（OpenAI 兼容）\n超时/重试/预算/脱敏/降级\n草稿库（唯一可写，与仓库分离）", "#F3F4F6", GREY, 8)
arrow(80, 24, 84, 40)
arrow(80, 19, 84, 25)
arrow(62, 42, 84, 32)
arrow(95.5, 22, 95.5, 17)
arrow(95.5, 35, 95.5, 38)
ax.text(55, 1.5, "数字只来自 SQL；LLM 只组织文字并经回查校验；Agent 只生成待人工审核的草稿，没有发送接口", ha="center", fontsize=9, color="#374151")
fig.tight_layout()
fig.savefig(out / "fig_architecture.png", dpi=DPI)
plt.close(fig)
used["fig_architecture"] = "docs/architecture.md + src/retail_bi 实际模块"

(out / "chart_sources.json").write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok", list(used))
