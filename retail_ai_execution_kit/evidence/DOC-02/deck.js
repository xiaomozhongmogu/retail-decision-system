// Build deliverables/midterm_slides.pptx from the project's structured result files.
// Usage: NODE_PATH=./node_modules node deck.js <project_root> <fig_dir> <out_pptx> <apply_theme.js>
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const [root, figDir, outFile, applyThemePath] = process.argv.slice(2);
const { applyTheme } = require(applyThemePath);
const J = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
const eda = J("reports/analysis/eda_initial.json");
const clus = J("reports/model/cluster_metrics.json");
const test = J("reports/model/test_metrics.json");
const sel = J("reports/model/model_selection.json");
const etl = J("reports/warehouse/etl_run.json");
const tasksRaw = J("project/tasks.json");
const nl2sql = J("reports/ai/nl2sql_evaluation.json");
const rag = J("reports/ai/rag_evaluation.json");
const agent = J("reports/ai/agent_evaluation.json");
const integ = J("reports/ai/integration_evaluation.json");
const reg = J("reports/release/test_summary.json");
const life = JSON.parse(fs.readFileSync(path.join(figDir, "lifecycle_latest.json"), "utf8"));

const T = Array.isArray(tasksRaw) ? tasksRaw : tasksRaw.tasks;
const nDone = T.filter((t) => t.status === "done").length;
const nSel = T.filter((t) => t.selected).length;
const regPassed = reg.checks.filter((r) => r.status === "passed").length;
const regTotal = reg.checks.length;
const p = test.scores.p_model, rf = test.scores.rule_frequency_90d, rr = test.scores.rule_recency;
const cv = sel.candidates_validation;
const dwd = etl.stages.find((s) => s.stage === "dwd").rows;
const snap = etl.stages.find((s) => s.stage === "snapshot");
const segs = clus.rule_segments.apply_as_of_profile;
const n0 = (x) => Number(x).toLocaleString("en-US");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";

const THEME = {
  name: "Retail Lifecycle",
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  colors: {
    dk1: "1F2A2E", lt1: "FFFFFF", dk2: "0F3D47", lt2: "EAF2F3",
    accent1: "0F3D47", accent2: "E8702A", accent3: "2E8B57", accent4: "7A8C91",
    accent5: "C0392B", accent6: "4C9AA8", hlink: "0F6E80", folHlink: "5B6B70",
  },
};
const K = THEME.colors;
const MUTED = "5B6B70";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "智能决策综合实践中期答辩";
pres.author = "信管4班5组";
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: K.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 1.5, w: 8.6, h: 1.3, fontSize: 32, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 3.0, w: 8.6, h: 1.6, fontSize: 16, color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: K.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7, fontSize: 26, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "数据完全合成，不代表真实企业 · 信管4班5组 · 中期检查", options: { x: 0.5, y: 5.25, w: 7.5, h: 0.25, fontSize: 9, color: MUTED, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.3, fontSize: 9, color: MUTED, align: "right" },
});

let objN = 0;
const on = (s) => `${s}-${++objN}`;
const text = (slide, t, o) => slide.addText(t, { isTextBox: true, margin: 0, fontSize: 14, color: K.dk1, valign: "top", objectName: on("text"), ...o });
const card = (slide, x, y, w, h, fill = K.lt2) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: on("card") });
const badge = (slide, x, y, label, fill = K.accent2) => {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: fill }, objectName: on("badge") });
  text(slide, label, { x, y, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: K.lt1, align: "center", valign: "middle" });
};
const stat = (slide, x, y, w, big, small, color = K.dk2) => {
  card(slide, x, y, w, 1.25);
  text(slide, big, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 0.62, fontSize: 30, bold: true, color, valign: "middle" });
  text(slide, small, { x: x + 0.15, y: y + 0.76, w: w - 0.3, h: 0.42, fontSize: 11, color: MUTED });
};
const bullets = (slide, items, o) => slide.addText(
  items.map((it, i) => ({ text: it, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
  { isTextBox: true, margin: 0, fontSize: 14, color: K.dk1, valign: "top", objectName: on("list"), ...o },
);
const chartBase = (title) => ({
  showTitle: true, title, titleFontSize: 12, titleColor: K.dk1, titleFontFace: "+mn-lt",
  catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  valGridLine: { color: "DDE3E5", size: 0.5 }, catGridLine: { style: "none" },
  dataLabelFontSize: 10, dataLabelColor: K.dk1,
});
const S = (sec, master = "CONTENT") => pres.addSlide({ masterName: master, sectionTitle: sec });

// 1 Title
pres.addSection({ title: "开场" });
let s = S("开场", "TITLE_DARK");
s.addText("基于用户全生命周期的电商零售智能决策与 AI 运营助手系统", { placeholder: "title" });
s.addText([
  { text: "中期检查答辩 · 第二阶段：模型设计与数据分析", options: { breakLine: true } },
  { text: "信管4班5组 · 李沁阳、李浩畅（组长）、黄思凯、李仕仁、孙卓", options: { breakLine: true } },
  { text: "2026 年 11 月 · 数据为完全合成的电商交易数据" },
], { placeholder: "body" });
s.addNotes("开场。介绍题目和本次中期汇报的范围：第二阶段要求完成模型设计与数据分析。先强调一点：我们用的是完全合成的电商交易数据，所有结论只说明系统在这份数据上的表现，不代表真实企业。");

// 2 Progress overview
s = S("开场");
s.addText("本阶段要求已完成，AI 与应用已提前实现", { placeholder: "title" });
stat(s, 0.5, 1.2, 2.1, `${nDone}/${nSel}`, "台账任务已按证据验收");
stat(s, 2.8, 1.2, 2.1, `${regPassed}/${regTotal}`, "关键路径回归通过");
stat(s, 5.1, 1.2, 2.1, "4 层", "数仓分层：ODS 至 ADS");
stat(s, 7.4, 1.2, 2.1, "3 个", "AI 模块已实现");
const prog = [
  ["数据预处理、数仓、EDA、分群、预测", "已完成", K.accent3],
  ["AI 三模块与五类页面（原计划终期）", "已实现 · 人工抽查待做", K.accent2],
  ["正式报告、终期 PPT、终期答辩", "未开始（12-22 截止）", K.accent4],
];
prog.forEach(([a, b, c], i) => {
  const y = 2.75 + i * 0.75;
  card(s, 0.5, y, 9.0, 0.6, "F6F8F8");
  s.addShape(pres.shapes.OVAL, { x: 0.68, y: y + 0.18, w: 0.24, h: 0.24, fill: { color: c }, line: { color: c }, objectName: on("dot") });
  text(s, a, { x: 1.1, y, w: 5.2, h: 0.6, valign: "middle" });
  text(s, b, { x: 6.3, y, w: 3.0, h: 0.6, valign: "middle", bold: true, color: c, align: "right" });
});
s.addNotes(`总体进展。台账共 ${nSel} 项任务，${nDone} 项已验收；验收看的是实际运行的结果文件和证据记录，不是代码写完。本阶段要求的数据分析和模型设计已经完成；AI 模块和页面按计划属于终期，我们提前做了。还没做的是正式报告、终期 PPT 和周报的人工抽查。`);

// 3 Architecture
pres.addSection({ title: "架构与数据" });
s = S("架构与数据");
s.addText("离线写、在线读：数字只来自 SQL", { placeholder: "title" });
const flow = [["原始包", "核对哈希"], ["清洗与规则", "质量门槛 10/10"], ["ODS / DWD", "星型模型"], ["DWS / ADS", "汇总 · 时点快照 · 指标视图"], ["只读发布", "版本化 DuckDB · 可回滚"]];
flow.forEach(([a, b], i) => {
  const x = 0.5 + i * 1.84;
  card(s, x, 1.25, 1.6, 1.05, i === 4 ? "E3F1E8" : K.lt2);
  text(s, a, { x: x + 0.1, y: 1.33, w: 1.4, h: 0.4, fontSize: 14, bold: true, color: K.dk2, align: "center" });
  text(s, b, { x: x + 0.1, y: 1.75, w: 1.4, h: 0.5, fontSize: 10, color: MUTED, align: "center" });
  if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.62, y: 1.67, w: 0.2, h: 0.22, fill: { color: K.accent4 }, line: { color: K.accent4 }, objectName: on("arrow") });
});
const online = [["五类页面", "数据口径 · 经营总览 · 客户 · 预测 · AI 工作台"], ["查询助手", "意图 → 白名单 SQL → 只读执行"], ["经营周报", "SQL 事实 → LLM 写文字 → 数字回查"], ["挽回 Agent", "画像 → 政策 → 预算 → 待审草稿"]];
online.forEach(([a, b], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 2.65 + Math.floor(i / 2) * 0.95;
  card(s, x, y, 4.4, 0.8, "F6F8F8");
  badge(s, x + 0.15, y + 0.19, String(i + 1), i === 0 ? K.accent1 : K.accent2);
  text(s, a, { x: x + 0.7, y: y + 0.08, w: 3.6, h: 0.32, fontSize: 14, bold: true, color: K.dk2 });
  text(s, b, { x: x + 0.7, y: y + 0.42, w: 3.6, h: 0.32, fontSize: 11, color: MUTED });
});
text(s, "LLM 只组织文字；Agent 没有发送接口，所有草稿须人工审核", { x: 0.5, y: 4.62, w: 9, h: 0.35, fontSize: 12, italic: true, color: K.accent2 });
s.addNotes("架构。左边一行是离线批处理，在命令行里跑：核对原始包哈希、清洗、建四层数仓，最后发布成一个只读的 DuckDB 文件，失败时保留上一版。下面是在线部分，页面和三个 AI 模块都只读这个发布文件。关键原则：数字只来自 SQL，大模型只负责组织文字，周报生成后会逐个回查数字；Agent 只能存草稿，没有发送接口。");

// 4 Data
s = S("架构与数据");
s.addText("数据：一份完全合成的交易包，边界写清楚", { placeholder: "title" });
stat(s, 0.5, 1.2, 2.1, n0(eda.volume.valid_orders), "有效订单（取消 " + eda.volume.cancelled_orders + "）");
stat(s, 0.5, 2.6, 2.1, n0(eda.volume.lines_all), "订单明细行");
stat(s, 2.8, 1.2, 2.1, n0(eda.volume.buyers), "有效购买客户");
stat(s, 2.8, 2.6, 2.1, "$" + (eda.volume.merch_usd / 1e6).toFixed(2) + "M", "商品金额，不含运费");
card(s, 5.15, 1.2, 4.35, 3.65, "F6F8F8");
text(s, "口径与边界", { x: 5.35, y: 1.32, w: 4, h: 0.35, fontSize: 15, bold: true, color: K.dk2 });
bullets(s, [
  "时间：2024-01-01 至 2026-11-07，源数据无时区，按 UTC 处理",
  "金额：USD，商品金额与运费分开",
  "没有数量列：删去销量件数类指标，不假设数量为 1",
  "截止日后才发生的收货、评价一律截掉",
  "合成数据的使用基于用户授权，尚待教师书面认可",
], { x: 5.35, y: 1.75, w: 4.0, h: 3.0, fontSize: 12 });
text(s, "预处理：导入（核对哈希）→ 剖析 → 清洗 → 交易规则 → 集成转换 → 质量门槛 10/10", { x: 0.5, y: 4.05, w: 4.4, h: 0.8, fontSize: 11, color: MUTED });
s.addNotes("数据。我们用一份完全合成的电商交易包，没有拼接其他来源。左边是规模；右边是口径：时间没有时区，按 UTC；金额是美元，运费分开；没有数量列，所以不做销量分析，也不假设每行数量为 1；截止日之后才发生的信息都截掉，防止未来信息进入分析。合成数据的使用还没有拿到老师书面认可，这是我们想在答辩时当面确认的。");

// 5 Warehouse
s = S("架构与数据");
s.addText("数仓：星型模型、一键重建、对账一致", { placeholder: "title" });
const hdr = (t) => ({ text: t, options: { bold: true, color: K.lt1, fill: { color: K.dk2 } } });
s.addTable([
  [hdr("层"), hdr("主要表"), hdr("行数")],
  ["DWD", "fact_order / fact_order_line", `${n0(dwd.fact_order)} / ${n0(dwd.fact_order_line)}`],
  ["DWD", "fact_payment / fact_fulfillment", `${n0(dwd.fact_payment)} / ${n0(dwd.fact_fulfillment)}`],
  ["DWD", "dim_customer / dim_product / dim_seller", `${n0(dwd.dim_customer)} / ${n0(dwd.dim_product)} / ${n0(dwd.dim_seller)}`],
  ["DWS", "日 × 地区 × 品类汇总、客户日、商品日", "金额合计与 DWD 一致"],
  ["DWS", "客户 × as_of 时点快照（每周）", `${n0(snap.coverage.rows)}（${snap.coverage.as_of_points} 个时点）`],
  ["ADS", "指标语义视图（白名单）", "页面与 AI 只读这些视图"],
], { x: 0.5, y: 1.2, w: 5.6, colW: [0.7, 3.0, 1.9], fontSize: 11, color: K.dk1, border: { type: "solid", pt: 0.5, color: "C9D3D6" }, rowH: 0.42, objectName: on("table") });
card(s, 6.4, 1.2, 3.1, 3.65, "F6F8F8");
text(s, "已验证", { x: 6.6, y: 1.32, w: 2.8, h: 0.35, fontSize: 15, bold: true, color: K.dk2 });
bullets(s, ["OLAP 上卷、下钻、切片、切块：与明细独立重算一致", "时点快照不读 as_of 之后的数据", "一条命令重建；注入失败不留半成品", "只读发布、原子切换、可回滚"], { x: 6.6, y: 1.75, w: 2.75, h: 3.0, fontSize: 12 });
s.addNotes("数仓。DWD 是星型模型：订单、明细、支付、履约四张事实表，加客户、商品、卖家、日期、地区维度。订单数按订单去重，不按明细行计数。DWS 里有一张客户乘时点的快照表，每周一个时点，只用当时之前的数据，后面建模就靠它防泄漏。右边是验证：OLAP 四类操作和从明细独立重算的结果一致，人为注入失败时不会留下半成品。");

// 6 Trend
pres.addSection({ title: "数据分析" });
s = S("数据分析");
s.addText("经营趋势：收入持平来自两股相反的力量", { placeholder: "title" });
const months = eda.monthly.filter((m) => m.month !== "2026-11");
s.addChart(pres.charts.BAR, [{ name: "商品金额（千 USD）", labels: months.map((m) => m.month), values: months.map((m) => +(m.merch_usd / 1000).toFixed(1)) }], {
  x: 0.5, y: 1.1, w: 6.0, h: 3.85, barDir: "col", chartColors: [K.accent6], showLegend: false, barGapWidthPct: 40,
  ...chartBase("月度商品金额（千 USD，2024-01 至 2026-10）"), catAxisLabelFontSize: 8, objectName: on("chart"),
});
card(s, 6.8, 1.1, 2.7, 1.2);
text(s, "−0.3%", { x: 6.95, y: 1.18, w: 2.4, h: 0.55, fontSize: 28, bold: true, color: K.dk2 });
text(s, "2026 年 1–10 月商品金额同比", { x: 6.95, y: 1.75, w: 2.4, h: 0.45, fontSize: 11, color: MUTED });
bullets(s, ["客户数减少：−11,689 USD", "客单价上升：+11,546 USD", "10–12 月为高峰，2 月最低", "新客减少是数据边界：客户都在 2024 上半年建档"], { x: 6.8, y: 2.5, w: 2.7, h: 2.4, fontSize: 12 });
s.addNotes("经营趋势。每年 10 到 12 月是高峰，2 月最低。2026 年前 10 个月商品金额同比只降了 0.3%，但拆开看，客户数减少拉低了约 1.17 万美元，客单价上升又补回了约 1.15 万美元。新客户逐年减少，是因为合成数据里的客户全都在 2024 年上半年建档，这是数据边界，不能说成获客能力下降。");

// 7 Lifecycle
s = S("数据分析");
s.addText("生命周期状态描述“多久没买”，不预示流失", { placeholder: "title" });
const LN = { new: "新客", active: "活跃", at_risk: "沉默预警", dormant: "沉睡" };
const LO = ["new", "active", "at_risk", "dormant"];
s.addChart(pres.charts.BAR, [{ name: "客户数", labels: LO.map((k) => LN[k]), values: LO.map((k) => life.counts[k]) }], {
  x: 0.5, y: 1.1, w: 5.0, h: 3.85, barDir: "col", chartColors: [K.accent3, K.accent1, K.accent2, K.accent4], showLegend: false, showValue: true, dataLabelPosition: "outEnd",
  ...chartBase(`最新时点各状态客户数（as_of ${life.as_of}）`), objectName: on("chart"),
});
card(s, 5.8, 1.1, 3.7, 1.45);
text(s, "≈ 35%", { x: 5.95, y: 1.18, w: 3.4, h: 0.6, fontSize: 30, bold: true, color: K.accent2 });
text(s, "四种状态客户未来 180 天的复购率都约为 35%，沉睡与活跃几乎相同", { x: 5.95, y: 1.8, w: 3.4, h: 0.7, fontSize: 11, color: MUTED });
bullets(s, [
  `30 天内复购只占全部购买间隔的 ${pct(eda.customers.gap_days.share_within_30d)}`,
  "cohort +1 月留存 6.7%–8.7%，各期 4%–9%",
  "状态只提示跟进时机，页面不用“高风险”",
], { x: 5.8, y: 2.8, w: 3.7, h: 2.1, fontSize: 12 });
s.addNotes("生命周期。按距最近购买的天数分新客、活跃、沉默预警、沉睡四种状态。但我们检查了每种状态未来 180 天的复购率，都在 35% 左右，沉睡客户和活跃客户几乎一样。所以状态只能说明多久没买、什么时候该跟进，不能当作流失风险。另外 30 天内复购只占约 11%，这也决定了后面预测任务的难度。");

// 8 RFM
s = S("数据分析");
s.addText(`约 ${pct(segs[1].share + segs[3].share, 0)} 的客户贡献约 ${pct(segs[1].m_total_share + segs[3].m_total_share, 0)} 的近 90 天金额`, { placeholder: "title" });
s.addChart(pres.charts.BAR, [
  { name: "客户占比 %", labels: segs.map((g) => g.segment.split("（")[0]), values: segs.map((g) => +(g.share * 100).toFixed(1)) },
  { name: "金额占比 %", labels: segs.map((g) => g.segment.split("（")[0]), values: segs.map((g) => +(g.m_total_share * 100).toFixed(1)) },
], {
  x: 0.5, y: 1.1, w: 5.6, h: 3.85, barDir: "col", chartColors: [K.accent4, K.accent1], showLegend: true, legendPos: "b", legendFontSize: 10, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
  ...chartBase(`RFM 规则分群（as_of ${clus.definition.as_of_apply.slice(0, 10)}，${clus.rows.apply} 人）`), objectName: on("chart"),
});
card(s, 6.4, 1.1, 3.1, 3.85, "F6F8F8");
text(s, "K-Means（k = 3–6）", { x: 6.6, y: 1.22, w: 2.8, h: 0.35, fontSize: 15, bold: true, color: K.dk2 });
bullets(s, [
  "规则事先定：最小群 ≥ 5%、重抽样 ARI ≥ 0.8，取轮廓系数最高",
  `k = 3 轮廓系数略高，但 ARI 只有 ${clus.kmeans.k_comparison["3"].bootstrap_ari_mean}`,
  `选 k = 4：ARI ${clus.kmeans.k_comparison["4"].bootstrap_ari_mean}`,
  "切分点只在训练期拟合；分群不作模型特征",
], { x: 6.6, y: 1.65, w: 2.75, h: 3.2, fontSize: 12 });
s.addNotes("客户分群。对近 90 天有购买的客户做 RFM。先用可解释的规则分四群：较早高价值和近期高价值两群约占 35% 的客户，却贡献约 69% 的近 90 天金额，是维系资源的优先对象。K-Means 作为补充，选 k 的规则是事先定好的：k 等于 3 的轮廓系数略高，但重抽样稳定性差，所以选 k 等于 4。切分点只在训练期拟合，避免泄漏。");

// 9 Model design
pres.addSection({ title: "预测模型" });
s = S("预测模型");
s.addText("复购预测：先定目标与防泄漏，再比模型", { placeholder: "title" });
const steps = [
  ["目标", "未来 30 天是否有有效购买"],
  ["母体", "每周一个时点；近 90 天有购买的客户"],
  ["特征", "只用时点之前的行为"],
  ["切分", "训练 / 验证 / 测试按时间，段间隔 5 周"],
  ["选模", "规则 → 逻辑回归 → LightGBM，看验证集"],
  ["测试", "冻结后只用一次"],
];
steps.forEach(([a, b], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 3.05, y = 1.2 + row * 1.25;
  card(s, x, y, 2.85, 1.05);
  badge(s, x + 0.15, y + 0.15, String(i + 1));
  text(s, a, { x: x + 0.7, y: y + 0.15, w: 2.0, h: 0.42, fontSize: 15, bold: true, color: K.dk2, valign: "middle" });
  text(s, b, { x: x + 0.15, y: y + 0.6, w: 2.6, h: 0.42, fontSize: 11, color: MUTED });
});
s.addTable([
  [hdr("验证集"), hdr("ROC-AUC"), hdr("PR-AUC"), hdr("Lift@10%")],
  ["规则：近 90 天订单数", cv.rule_frequency_90d.roc_auc.toFixed(3), cv.rule_frequency_90d.pr_auc.toFixed(4), cv.rule_frequency_90d["lift@10%"].toFixed(2)],
  [{ text: "逻辑回归（选定）", options: { bold: true } }, cv.logreg.roc_auc.toFixed(3), { text: cv.logreg.pr_auc.toFixed(4), options: { bold: true } }, cv.logreg["lift@10%"].toFixed(2)],
  ["LightGBM（调参后）", cv.lightgbm_best.roc_auc.toFixed(3), cv.lightgbm_best.pr_auc.toFixed(4), cv.lightgbm_best["lift@10%"].toFixed(2)],
], { x: 0.5, y: 3.8, w: 9.0, colW: [3.3, 1.9, 1.9, 1.9], fontSize: 11, color: K.dk1, border: { type: "solid", pt: 0.5, color: "C9D3D6" }, rowH: 0.3, objectName: on("table") });
s.addNotes(`模型设计。目标是未来 30 天是否复购；每周取一个时点，母体是近 90 天有购买的客户；特征只用时点之前的行为。训练、验证、测试按时间切开，中间隔 5 周，保证标签成熟后才进入下一段。选模看验证集：逻辑回归 PR-AUC ${cv.logreg.pr_auc.toFixed(4)}，LightGBM ${cv.lightgbm_best.pr_auc.toFixed(4)}，差不多，所以选更简单可解释的逻辑回归，冻结后才碰测试集，而且只用一次。`);

// 10 Test result
s = S("预测模型");
s.addText("测试结果：个体区分接近随机，我们如实报告", { placeholder: "title" });
stat(s, 0.5, 1.15, 2.9, p.roc_auc.toFixed(3), `ROC-AUC，95% 区间 [${p.roc_auc_95ci.join(", ")}] 含 0.5`, K.accent5);
stat(s, 0.5, 2.47, 2.9, p["weekly_lift@10%"].toFixed(2), "周内 Lift@10%（随机 = 1.0）", K.accent5);
stat(s, 0.5, 3.79, 2.9, String(p.ece), `ECE：平均概率可信（预测 ${pct(p.mean_pred)}，实际 ${pct(p.positive_rate)}）`, K.accent3);
s.addChart(pres.charts.BAR, [{ name: "周内 Lift@10%", labels: ["逻辑回归", "规则：90 天订单数", "规则：最近购买"], values: [p, rf, rr].map((x) => +x["weekly_lift@10%"].toFixed(2)) }], {
  x: 3.7, y: 1.2, w: 5.8, h: 2.6, barDir: "col", chartColors: [K.accent5, K.accent4, K.accent4], showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1.3, valAxisLabelFormatCode: "0.0",
  ...chartBase(`时间外测试：${n0(test.test_set.rows)} 行 / ${n0(test.test_set.customers)} 名客户，正例 ${pct(test.test_set.positive_rate)}`), objectName: on("chart"),
});
card(s, 3.7, 4.0, 5.8, 0.9, "FBEDE3");
text(s, "怎么用：名单按价值、频次等规则排序并说明其效果也接近随机；模型只给整体复购水平；不宣称精准预测或挽回效果", { x: 3.85, y: 4.07, w: 5.5, h: 0.78, fontSize: 12, color: K.dk1, valign: "middle" });
s.addNotes(`测试结果，这是本阶段最重要的一页。测试集 ROC-AUC ${p.roc_auc.toFixed(3)}，95% 区间包含 0.5；每周挑前 10% 客户，模型的 Lift 是 ${p["weekly_lift@10%"].toFixed(2)}，比随机还低一点，规则也只有 1 左右。也就是说，模型和规则都挑不出这周最可能复购的人。但平均概率是可信的，校准误差只有 ${p.ece}。原因是合成数据里复购和历史行为几乎没关系。我们没有为了好看去换目标或换测试集，而是据此规定模型只能当整体水平参考。`);

// 11 AI modules
pres.addSection({ title: "AI 与应用" });
s = S("AI 与应用");
s.addText("AI 三模块已实现，并经过独立出题与对抗测试", { placeholder: "title" });
const ai = [
  ["查询助手", `可回答 ${pct(nl2sql.answerable_accuracy, 0)}，越权/歧义拦截 ${nl2sql.refusal_cases_blocked}/${nl2sql.refusal_cases_total}`, "全新问法首测 80%–86%"],
  ["经营周报", "对抗输入 25/25 拦截；盲测 10/10 拦截、0/14 误判", "人工抽查（≥5 份）待做"],
  ["挽回 Agent", `${agent.passed}/${agent.cases} 场景通过（${agent.live_llm_cases} 个真实调用）`, "只存草稿，须人工审核"],
  ["知识检索 / 联调", `检索 ${rag.passed}/${rag.cases}；三模块联调 ${integ.passed}/${integ.total}`, "LLM 答案文字有波动"],
];
ai.forEach(([a, b, c], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.2 + Math.floor(i / 2) * 1.85;
  card(s, x, y, 4.4, 1.65);
  badge(s, x + 0.2, y + 0.2, String(i + 1), K.accent1);
  text(s, a, { x: x + 0.8, y: y + 0.2, w: 3.4, h: 0.42, fontSize: 16, bold: true, color: K.dk2, valign: "middle" });
  text(s, b, { x: x + 0.2, y: y + 0.75, w: 4.0, h: 0.42, fontSize: 12 });
  text(s, "限制：" + c, { x: x + 0.2, y: y + 1.17, w: 4.0, h: 0.35, fontSize: 11, color: K.accent2 });
});
s.addNotes("AI 模块。按计划属于终期，我们已经实现：查询助手把问题解析成结构化意图，再由程序拼白名单 SQL 只读执行；周报的数字由 SQL 算好，大模型写文字后逐个回查；挽回 Agent 只能存草稿。测试方面，我们请 GPT 和 Gemini 独立出题和做对抗测试，并报告首测成绩：查询助手对全新问法首测只有 80% 到 86%。周报的人工抽查还没做，这些都是 AI 测试，不当作人工测试。");

// 12 Screenshots
s = S("AI 与应用");
s.addText("系统实际运行截图", { placeholder: "title" });
const shots = [["evidence/UI-05/test_results_browser.jpg", "复购预测页：测试结果与使用边界"], ["evidence/UI-06/query_assistant_live.jpg", "AI 工作台：查询助手（真实 LLM 调用）"]];
shots.forEach(([f, cap], i) => {
  const x = 0.5 + i * 4.6;
  s.addImage({ path: path.join(root, f), x, y: 1.15, w: 4.4, h: 4.4 * 514 / 800, altText: cap, objectName: on("shot") });
  text(s, cap, { x, y: 1.15 + 4.4 * 514 / 800 + 0.08, w: 4.4, h: 0.3, fontSize: 11, color: MUTED, align: "center" });
});
s.addNotes("截图来自浏览器中实际运行的系统。左边是复购预测页，直接写出测试结果和使用边界；右边是查询助手的一次真实调用，答案下面可以展开看执行的 SQL 和证据。现场我们会实际演示，而不是只放截图。");

// 13 Risks
pres.addSection({ title: "问题与计划" });
s = S("问题与计划");
s.addText("当前问题与风险", { placeholder: "title" });
const risks = [
  ["数据口径", "教师尚未书面认可合成数据与时效", "答辩当面说明；报告注明“完全合成”"],
  ["模型效果", "个体区分接近随机", "如实报告；名单用规则排序"],
  ["人工评测", "周报人工抽查未做", "组员按抽查方案复核 ≥ 5 份"],
  ["现场演示", "依赖网络与 LLM；新问法可能答不了", "自动降级；周报回放；备用截图"],
  ["复现与分工", "只在 macOS 验证；非技术分工未定", "终期前在 Windows 试装；本周定分工"],
];
s.addTable([[hdr("方面"), hdr("问题 / 风险"), hdr("处理")], ...risks], { x: 0.5, y: 1.2, w: 9.0, colW: [1.5, 3.6, 3.9], fontSize: 12, color: K.dk1, border: { type: "solid", pt: 0.5, color: "C9D3D6" }, rowH: 0.62, valign: "middle", objectName: on("table") });
s.addNotes("问题与风险。第一是数据口径，老师还没书面认可合成数据，我们希望今天能得到意见。第二是模型效果弱，我们如实报告。第三是周报人工抽查还没做。第四是现场演示依赖网络和大模型，无密钥或超时会自动降级为规则和模板，周报可以回放已记录的文本，另外备好截图。第五是复现只在 Mac 上验证过，以及文档和答辩的分工还要尽快定下来。");

// 14 Schedule
s = S("问题与计划");
s.addText("终期排期：12-13 冻结，12-22 答辩", { placeholder: "title" });
const sch = [
  ["11-30", "中期报告与答辩", "保存提交回执"],
  ["12-07", "人工抽查；分工与个人贡献", "抽查记录入库"],
  ["12-13", "正式报告六章；冻结版本并打包", "打包清单与哈希"],
  ["12-18", "终期 PPT、讲稿与演练", "每人能答 1–2 题"],
  ["12-22", "提交正式报告；现场答辩", "记录真实结果"],
];
s.addShape(pres.shapes.LINE, { x: 0.9, y: 2.15, w: 8.2, h: 0, line: { color: K.accent4, width: 1.5 }, objectName: on("timeline") });
sch.forEach(([d, a, b], i) => {
  const x = 0.5 + i * 1.84;
  s.addShape(pres.shapes.OVAL, { x: x + 0.62, y: 2.0, w: 0.3, h: 0.3, fill: { color: i === 0 ? K.accent2 : K.dk2 }, line: { color: K.lt1, width: 2 }, objectName: on("node") });
  text(s, d, { x, y: 1.3, w: 1.55, h: 0.5, fontSize: 18, bold: true, color: i === 0 ? K.accent2 : K.dk2, align: "center", valign: "middle" });
  card(s, x, 2.6, 1.6, 1.75, "F6F8F8");
  text(s, a, { x: x + 0.12, y: 2.72, w: 1.36, h: 1.2, fontSize: 13, bold: true, color: K.dk1 });
  text(s, b, { x: x + 0.12, y: 3.75, w: 1.36, h: 0.5, fontSize: 11, color: MUTED });
});
s.addNotes("终期排期。11 月 30 日前完成中期报告和答辩；12 月 7 日前完成周报人工抽查和分工；12 月 13 日完成正式报告并冻结代码、数据和模型；12 月 18 日前完成终期 PPT、讲稿和全流程演练；12 月 22 日提交并答辩。");

// 15 Close
pres.addSection({ title: "结束" });
s = S("结束", "TITLE_DARK");
s.addText("接下来：现场演示与问答", { placeholder: "title" });
s.addText([
  { text: "演示：经营总览 → 生命周期 → 复购预测 → 查询助手 → 挽回 Agent", options: { breakLine: true } },
  { text: "想请老师确认：合成数据与数据时效能否作为正式口径", options: { breakLine: true } },
  { text: "复现命令与证据索引见中期报告附录" },
], { placeholder: "body" });
s.addNotes("结束。接下来现场演示，顺序是经营总览、生命周期、复购预测、查询助手、挽回 Agent。最后想请老师确认：合成数据和数据时效能否作为正式口径。谢谢老师。");

(async () => {
  await pres.writeFile({ fileName: outFile });
  await applyTheme(outFile, THEME);
  console.log("wrote", outFile);
})();
