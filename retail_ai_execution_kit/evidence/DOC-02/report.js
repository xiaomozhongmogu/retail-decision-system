// Build deliverables/midterm_report.docx. Key numbers are read from the project's structured result files.
// Usage: node report.js <project_root> <fig_dir> <out_docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  HeadingLevel, ShadingType, BorderStyle, PageBreak, Footer, PageNumber, LevelFormat, TableOfContents,
} = require("docx");

const [root, figDir, outFile] = process.argv.slice(2);
const J = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
const eda = J("reports/analysis/eda_initial.json");
const clus = J("reports/model/cluster_metrics.json");
const test = J("reports/model/test_metrics.json");
const sel = J("reports/model/model_selection.json");
const etl = J("reports/warehouse/etl_run.json");
const tasks = J("project/tasks.json");
const nl2sql = J("reports/ai/nl2sql_evaluation.json");
const rag = J("reports/ai/rag_evaluation.json");
const agent = J("reports/ai/agent_evaluation.json");
const integ = J("reports/ai/integration_evaluation.json");
const reg = J("reports/release/test_summary.json");
const life = J(path.relative(root, path.join(figDir, "lifecycle_latest.json")));
const cur = J("warehouse/releases/current.json");

const T = Array.isArray(tasks) ? tasks : tasks.tasks;
const sel_ = T.filter((t) => t.selected !== false && t.status !== "skipped");
const nDone = T.filter((t) => t.status === "done").length;
const nSel = T.filter((t) => t.selected).length;
const regPassed = reg.checks.filter((r) => r.status === "passed").length;
if (regPassed !== reg.totals.passed) throw new Error("regression totals mismatch");
const regTotal = reg.checks.length;

const f2 = (x) => Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const n0 = (x) => Number(x).toLocaleString("en-US");
const pct = (x, d = 1) => (x * 100).toFixed(d) + "%";
const p = test.scores.p_model, rf = test.scores.rule_frequency_90d, rr = test.scores.rule_recency, br = test.scores.base_rate;
const cv = sel.candidates_validation;

// ---------- formatting helpers ----------
const FONT = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "宋体", cs: "Times New Roman" };
const HFONT = { ascii: "Arial", hAnsi: "Arial", eastAsia: "黑体", cs: "Arial" };
const run = (text, o = {}) => new TextRun({ text, font: o.h ? HFONT : FONT, size: o.size || 24, bold: o.bold, color: o.color, italics: o.it });
const para = (text, o = {}) => new Paragraph({
  children: Array.isArray(text) ? text : [run(text, o)],
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { line: 360, before: o.before || 0, after: o.after ?? 80 },
  indent: o.noIndent ? undefined : { firstLine: 480 },
});
const rich = (parts, o = {}) => para(parts.map((s) => (typeof s === "string" ? run(s) : run(s.t, { bold: s.b, color: s.c }))), o);
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run(t, { h: true, size: 30, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(t, { h: true, size: 26, bold: true })] });
const bullet = (text) => new Paragraph({
  numbering: { reference: "bul", level: 0 }, spacing: { line: 340, after: 40 },
  children: Array.isArray(text) ? text.map((s) => (typeof s === "string" ? run(s) : run(s.t, { bold: s.b }))) : [run(text)],
});
const caption = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 }, children: [run(t, { size: 20, h: true })] });
let figNo = 0, tabNo = 0;
const figure = (file, wPx, hPx, title, widthIn = 6.1) => {
  figNo += 1;
  const w = Math.round(widthIn * 96), h = Math.round((w * hPx) / wPx);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, children: [new ImageRun({ type: file.endsWith(".png") ? "png" : "jpg", data: fs.readFileSync(file), transformation: { width: w, height: h } })] }),
    caption(`图 ${figNo}  ${title}`),
  ];
};
const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
const TABLE_W = 9026;
const table = (title, header, rows, widths) => {
  tabNo += 1;
  const tot = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map((w) => Math.round((w / tot) * TABLE_W));
  ws[ws.length - 1] += TABLE_W - ws.reduce((a, b) => a + b, 0);
  const cell = (t, i, head) => new TableCell({
    borders, width: { size: ws[i], type: WidthType.DXA },
    shading: head ? { fill: "DCE6F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: String(t).split("\n").map((line) => new Paragraph({ spacing: { line: 280 }, children: [run(line, { size: 19, bold: head, h: head })] })),
  });
  return [
    caption(`表 ${tabNo}  ${title}`),
    new Table({
      width: { size: TABLE_W, type: WidthType.DXA }, columnWidths: ws,
      rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }), ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, i, false)) }))],
    }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
};
const fig = (n) => path.join(figDir, n);
const shot = (p_) => path.join(root, p_);

// ---------- content ----------
const dwd = etl.stages.find((s) => s.stage === "dwd").rows;
const dws = etl.stages.find((s) => s.stage === "dws").rows_and_merch;
const snap = etl.stages.find((s) => s.stage === "snapshot");
const segs = clus.rule_segments.apply_as_of_profile;
const kc = clus.kmeans.k_comparison;
const L = life.counts;

const cover = [
  new Paragraph({ spacing: { before: 1600 }, alignment: AlignmentType.CENTER, children: [run("华南农业大学", { h: true, size: 40, bold: true })] }),
  new Paragraph({ spacing: { before: 300, after: 900 }, alignment: AlignmentType.CENTER, children: [run("智能决策综合实践  中期检查报告", { h: true, size: 36, bold: true })] }),
  ...[
    ["题    目", "基于用户全生命周期的电商零售智能决策与 AI 运营助手系统"],
    ["组    别", "信管4班5组"],
    ["成    员", "李沁阳、李浩畅（组长）、黄思凯、李仕仁、孙卓"],
    ["阶    段", "第二阶段：模型设计与数据分析（2026-11-10 至 2026-11-30）"],
    ["日    期", "2026 年 11 月"],
  ].map(([k, v]) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 }, children: [run(k + "：", { h: true, size: 26, bold: true }), run(v, { size: 26 })] })),
  new Paragraph({ spacing: { before: 900 }, alignment: AlignmentType.CENTER, children: [run("成员名单与顺序取自已提交的选题报告表头；分工见第十一节。", { size: 20, color: "555555" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [run("本报告所有数据均为完全合成的电商交易数据，不代表真实企业或顾客。", { size: 20, color: "555555" })] }),
  new Paragraph({ children: [new PageBreak()] }),
];

const toc = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run("目  录", { h: true, size: 30, bold: true })] }),
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [run("（在 Word 中右键目录选择“更新域”即可刷新页码。）", { size: 18, color: "777777" })] }),
  new Paragraph({ children: [new PageBreak()] }),
];

const s1 = [
  H1("一、阶段目标与总体进展"),
  para("按选题报告的课程实习计划，第二阶段（2026-11-10 至 2026-11-30）的任务是：围绕主题完成模型设计与数据分析，提交中期检查报告，并参加现场答辩。本报告汇报截至撰写时已经实际完成并验证的工作、尚未完成的工作、遇到的问题与风险，以及终期（2026-12-22）前的安排。"),
  para(`项目用一份任务台账管理全部工作（project/tasks.json）。台账共列入 ${nSel} 项任务，其中 ${nDone} 项已按验收条件和证据记录验收；可选加分项（销量预测、关联规则等）未启用。本阶段要求的数据分析与模型设计已经完成；按原计划属于终期的 AI 模块和可视化应用也已提前实现，并做了自动化评测。下表列出各模块的实际状态。`),
  ...table("各模块实际状态（截至 2026-11-18）", ["模块", "状态", "主要结果", "证据位置"], [
    ["数据选择与预处理", "已完成", `合成交易包全量导入；订单明细 ${n0(eda.volume.lines_all)} 行；清洗后质量门槛 10/10`, "reports/data/、evidence/DATA-*"],
    ["数据仓库与 OLAP", "已完成", "ODS→DWD→DWS→ADS 四层；一键重建；只读发布与回滚；OLAP 结果与明细独立重算一致", "reports/warehouse/、evidence/DW-*"],
    ["探索性分析与诊断", "已完成", "趋势、量价分解、cohort 留存、生命周期规则、决策简报", "reports/analysis/、evidence/EDA-*"],
    ["客户分群", "已完成", "RFM 规则分群（4 群）＋K-Means（k=4）", "reports/model/rfm_segments.md"],
    ["复购预测", "已完成（负结果）", `时间外测试 ROC-AUC ${p.roc_auc.toFixed(3)}，个体区分接近随机，如实报告`, "reports/model/evaluation.md"],
    ["AI 三模块", "已实现并自动评测；人工抽查待完成", "查询助手、经营周报、挽回策略 Agent；真实 LLM 调用成功", "reports/ai/、evidence/AI-*"],
    ["可视化应用", "已完成", "Streamlit 五类页面；浏览器截图核验", "evidence/UI-*"],
    ["回归与复现", "已完成", `关键路径回归 ${regPassed}/${regTotal} 通过；GitHub 全新克隆按说明复现（仅 macOS arm64）`, "reports/release/"],
    ["正式报告、终期 PPT、答辩", "未开始", "终期阶段任务，见第十节", "—"],
  ], [2.2, 1.6, 4.2, 2.4]),
  rich([{ t: "关于“已完成”的口径：", b: true }, "本报告中的“已完成”指该任务在台账中已验收，验收依据是实际运行产生的结果文件和带哈希的证据记录，而不是“代码已写完”。用 AI 工具完成的测试（GPT、Gemini 的对抗与模拟用户测试）都标为 AI 测试，不当作人工测试。"]),
];

const s2 = [
  H1("二、系统架构与数据流"),
  para("系统分为离线批处理和在线只读两部分（图 1）。离线部分在命令行中运行：从核对过哈希的原始数据包开始，经导入、清洗、交易规则处理，逐层构建 ODS、DWD、DWS、ADS，再生成特征与标签、训练和评分，最后发布为一个带版本号的只读 DuckDB 文件。在线部分是 Streamlit 应用和 AI 工具层，只以只读方式打开发布文件；唯一可写的是与数据仓库分开的草稿库。"),
  ...figure(fig("fig_architecture.png"), 2200, 1040, "系统架构与数据流（与 src/retail_bi 实际模块一致）"),
  para("三条设计原则在实现中都有对应的检查：一是离线写、在线读，页面不运行 ETL 和训练；二是发布原子化，新版本通过对账后才切换，失败保留上一版；三是数字只来自 SQL，大模型只组织文字，生成后逐个回查数字。"),
  ...table("技术栈（版本以 requirements.lock 为准）", ["用途", "选择", "说明"], [
    ["运行环境", "Python 3.12（uv 管理）", "macOS arm64 实测；Windows/Intel 未验证"],
    ["存储与 SQL", "DuckDB 单文件＋Parquet", "嵌入式 OLAP，支持只读连接，无需数据库服务"],
    ["数据处理", "pandas、pyarrow", "读取 CSV、Parquet"],
    ["机器学习", "scikit-learn、LightGBM", "K-Means、逻辑回归、梯度提升树"],
    ["可视化与应用", "Streamlit、Plotly", "五类页面"],
    ["大模型接入", "OpenAI 兼容接口（当前为 DeepSeek）", "超时、重试、预算、脱敏、无密钥降级"],
    ["知识检索", "BM25/TF-IDF", "语料几十条，不需要向量数据库"],
    ["测试", "pytest＋自写回归运行器", "数据、数仓、模型、AI、页面关键路径"],
  ], [2, 3, 5]),
];

const s3 = [
  H1("三、数据选择与预处理"),
  H2("3.1 数据来源与边界"),
  para(`主数据是一份完全合成的电商交易数据包（baseline_10000_seed42，SHA-256 d50ee64a…7a16），走交易分析路线。候选的公开数据（UCI Online Retail II 等）时间较早，也不能覆盖“全生命周期”分析所需的履约、评价等信息，因此没有采用，也没有拼接其他来源的用户编号。这一选择基于用户授权的工作假设（项目决策 D012、D013），尚未取得教师对数据时效与合成数据的书面答复，报告中始终注明“完全合成”。`),
  ...table("数据边界", ["项目", "处理方式"], [
    ["时间范围", `${eda.scope.period}`],
    ["时区", "源数据没有时区，按 UTC 作为工程假设"],
    ["有效购买", "截止前已审批的订单（transaction-rules-v1）；取消单单列"],
    ["金额", "USD；商品金额与运费分开，支付金额只用于对账，不称营收"],
    ["数量", "源数据没有购买数量列，删除销量件数类指标，不假设每行数量为 1"],
    ["时间可得性", "按下单时间截取订单后，收货、评价等在截止日之后才发生的信息一律截掉，防止“未来信息”进入分析"],
  ], [2, 8]),
  H2("3.2 预处理步骤"),
  bullet("导入：从原始 ZIP 按文本重建（保留邮编前导零），校验哈希，同版本重复导入结果一致，篡改则拒绝覆盖。"),
  bullet("质量剖析：清洗前逐字段统计缺失、类型、重复和取值范围（reports/data/profile_before.md）。"),
  bullet("清洗：处理缺失、类型和重复，无法修复的行进入隔离区（本数据隔离 0 行）。"),
  bullet("交易规则：定义有效购买、取消、金额口径，并与原始金额逐项对账。"),
  bullet("集成与转换：订单、明细、支付、履约、评价、客户、商品关联，生成分析字段。"),
  bullet("质量门槛：清洗后 10 项检查全部通过（tests/data/quality_gate.py）。"),
  ...table("数据规模（截止 2026-11-08，不含当天）", ["指标", "数值"], [
    ["订单（全部 / 有效 / 取消）", `${n0(eda.volume.orders_all)} / ${n0(eda.volume.valid_orders)} / ${n0(eda.volume.cancelled_orders)}`],
    ["订单明细行", n0(eda.volume.lines_all)],
    ["客户（主数据 / 有有效购买）", `${n0(eda.volume.customers_master)} / ${n0(eda.volume.buyers)}`],
    ["售出商品种类", n0(eda.volume.products_sold)],
    ["有效商品金额 / 运费（USD）", `${f2(eda.volume.merch_usd)} / ${f2(eda.volume.shipping_usd)}`],
  ], [5, 5]),
];

const s4 = [
  H1("四、数据仓库与 OLAP"),
  para("数仓采用星型模型，按 ODS、DWD、DWS、ADS 分层（表 5）。订单数按订单去重计数，不按明细行计数；客户时点快照只使用 as_of 之前的事件，保证建模不读到未来数据。"),
  ...table("数仓各层与实际行数（DW-07 一键重建记录）", ["层", "表", "粒度", "行数"], [
    ["DWD", "fact_order / fact_order_line", "一张订单 / 一条明细", `${n0(dwd.fact_order)} / ${n0(dwd.fact_order_line)}`],
    ["DWD", "fact_payment / fact_fulfillment", "一笔支付 / 一张订单的履约", `${n0(dwd.fact_payment)} / ${n0(dwd.fact_fulfillment)}`],
    ["DWD", "dim_customer / dim_product / dim_seller", "维度", `${n0(dwd.dim_customer)} / ${n0(dwd.dim_product)} / ${n0(dwd.dim_seller)}`],
    ["DWD", "dim_date / dim_geo", "日历日 / 地区", `${n0(dwd.dim_date)} / ${n0(dwd.dim_geo)}`],
    ["DWS", "orders_daily_region / sales_daily_category_region", "日×地区 / 日×品类×地区", `${n0(dws.orders_daily_region[0])} / ${n0(dws.sales_daily_category_region[0])}`],
    ["DWS", "customer_daily / product_daily", "客户×日 / 商品×日", `${n0(dws.customer_daily[0])} / ${n0(dws.product_daily[0])}`],
    ["DWS", "客户时点快照", "客户×as_of（每周）", `${n0(snap.coverage.rows)}（${snap.coverage.as_of_points} 个时点）`],
    ["ADS", "指标语义视图", "按指标定义", `${cur.allowed_views.length} 个对外视图`],
  ], [1, 4, 3, 2.4]),
  para(`各 DWS 汇总表的商品金额合计都是 ${f2(dws.orders_daily_region[1])} USD，与 DWD 明细一致。OLAP 标准查询集覆盖上卷、下钻、切片、切块四类操作，结果与从 DWD 独立重算的结果一致（evidence/DW-08）。整套重建由一条命令完成；人为注入失败时不会留下半成品，发布指针仍指向上一版（evidence/DW-07、DW-10）。`),
];

const s5 = [
  H1("五、数据分析"),
  H2("5.1 经营趋势"),
  ...figure(fig("fig_monthly.png"), 2000, 800, "月度有效订单与商品金额"),
  para(`按年看，2024、2025 年月均有效订单 ${eda.by_year["2024"].orders_per_month}、${eda.by_year["2025"].orders_per_month} 单，2026 年前 10 个月为 ${eda.by_year["2026"].orders_per_month} 单。每年 10–12 月是高峰，2 月最少。2026 年 1–10 月商品金额同比 −0.3%：客户数减少的影响为 −11,689 USD，被客单价上升的 +11,546 USD 基本抵消（reports/analysis/diagnosis.md）。新购买客户逐期减少，原因是合成数据中的客户全部在 2024 年上半年建档，属于数据边界，不能解读为获客能力下降。`),
  H2("5.2 金额分布与客户集中度"),
  para(`每单商品金额中位数 ${eda.order_value.p50} USD，P90 为 ${eda.order_value.p90} USD，呈明显右偏。金额最高的 10% 客户贡献 ${pct(eda.concentration.top10pct_customers_share)} 的金额，最高的 20% 贡献 ${pct(eda.concentration.top20pct_customers_share)}。`),
  H2("5.3 复购与 cohort 留存"),
  para(`${n0(eda.customers.repeat.buyers)} 名有效购买客户中，${pct(eda.customers.repeat.repeat_share)} 买过至少两次；但相邻两次购买的间隔中位数约 ${Math.round(eda.customers.gap_days.p50)} 天，30 天内再次购买只占 ${pct(eda.customers.gap_days.share_within_30d)}。按首次可观测购买月份分 cohort，+1 月留存在 6.7%–8.7% 之间，各期都在 4%–9%，没有出现“首月高、之后下降”的典型形状（reports/analysis/cohort.md）。`),
  H2("5.4 生命周期状态"),
  para("按距最近一次有效购买的天数划分四种状态：首购 30 天内为新客，90 天内为活跃，90–180 天为沉默预警，超过 180 天为沉睡（docs/lifecycle_rules.md）。规则在 13 个边界用例上验证通过，并与数仓快照逐行一致。"),
  ...figure(fig("fig_lifecycle.png"), 1200, 680, "最新时点的生命周期状态分布", 4.4),
  rich([{ t: "关键发现：", b: true }, "各状态客户未来 180 天的复购率都约为 35%，沉睡客户与活跃客户几乎相同。因此生命周期状态只能描述“多久没买”，提示跟进时机，不能当作流失风险，页面上也不使用“高风险”的说法。"]),
];

const s6 = [
  H1("六、客户分群"),
  para(`分群对象是近 90 天有购买的客户（近 90 天没有购买的客户由生命周期规则管理）。R 为距最近购买天数，F 为近 90 天订单数，M 为近 90 天商品金额。切分点和标准化参数只在训练期最后一个时点（${clus.definition.as_of_fit.slice(0, 10)}）拟合，再应用到最新时点（${clus.definition.as_of_apply.slice(0, 10)}，${clus.rows.apply} 人）。`),
  H2("6.1 可解释的规则分群"),
  ...figure(fig("fig_rfm.png"), 1400, 720, "RFM 规则分群的客户占比与金额占比", 5.4),
  para(`“较早高价值”和“近期高价值”两群合计 ${pct(segs[1].share + segs[3].share)} 的客户，贡献了 ${pct(segs[1].m_total_share + segs[3].m_total_share)} 的近 90 天金额，是维系资源的优先对象。`),
  H2("6.2 K-Means 聚类"),
  para("对 R、F、M 取 log1p 后标准化，比较 k = 3–6。选择规则事先确定：最小群占比不低于 5%、重抽样平均 ARI 不低于 0.8 的 k 中，取轮廓系数最高者。"),
  ...table("K-Means 候选比较", ["k", "轮廓系数", "最小群占比", "重抽样 ARI 均值 / 最小"],
    Object.entries(kc).map(([k, v]) => [k + (Number(k) === clus.kmeans.k_chosen ? "（选定）" : ""), String(v.silhouette), pct(v.min_cluster_share), `${v.bootstrap_ari_mean} / ${v.bootstrap_ari_min}`]),
    [1.5, 2, 2, 3]),
  para("k = 3 的轮廓系数略高，但重抽样稳定性差（ARI 均值 0.49），因此选 k = 4。四个群按实际 R/F/M 中位数命名，例如“较早·单单·高金额”。聚类只描述客户结构，没有用作复购模型的特征。"),
];

const s7 = [
  H1("七、复购预测：模型设计与评估"),
  H2("7.1 预测目标与样本设计"),
  ...table("预测任务定义", ["项目", "定义"], [
    ["目标", "未来 30 天内是否有有效购买（y = 1 为复购）"],
    ["母体", "每周一个时点 as_of；过去 90 天有有效购买的客户"],
    ["特征", "只用 as_of 之前的历史行为：最近购买间隔、近 90 天订单/商品/品类数、累计金额、履约与评价等"],
    ["切分", "按时间切为训练、验证、测试三段，段间隔 5 周，标签成熟后才进入下一段"],
    ["防泄漏", "预处理参数只在训练集拟合；生成器标签、最终订单状态等不作特征；有单元测试"],
    ["测试集", "只在最终评估时使用一次；模型、校准与名单规则先冻结"],
  ], [2, 8]),
  H2("7.2 基线与选模（验证集）"),
  para("先建立规则基线（最近购买、近 90 天订单数），再比较逻辑回归和 LightGBM。"),
  ...table("验证集结果（测试集未使用）", ["模型", "ROC-AUC", "PR-AUC", "Lift@10%", "Brier"], [
    ["基率常数", "0.5", cv.logreg.positive_rate.toFixed(4), "—", "—"],
    ["规则：近 90 天订单数", cv.rule_frequency_90d.roc_auc.toFixed(4), cv.rule_frequency_90d.pr_auc.toFixed(4), cv.rule_frequency_90d["lift@10%"].toFixed(2), "非概率"],
    ["逻辑回归", cv.logreg.roc_auc.toFixed(4), cv.logreg.pr_auc.toFixed(4), cv.logreg["lift@10%"].toFixed(2), cv.logreg.brier.toFixed(4)],
    ["LightGBM（调参后最优）", cv.lightgbm_best.roc_auc.toFixed(4), cv.lightgbm_best.pr_auc.toFixed(4), cv.lightgbm_best["lift@10%"].toFixed(2), cv.lightgbm_best.brier.toFixed(4)],
  ], [3, 1.6, 1.6, 1.6, 1.6]),
  para(`逻辑回归验证集 PR-AUC ${cv.logreg.pr_auc.toFixed(4)}，略高于 LightGBM 的 ${cv.lightgbm_best.pr_auc.toFixed(4)}，因此选更简单、可解释的逻辑回归，冻结为 repurchase-logreg-v1。`),
  H2("7.3 时间外测试"),
  para(`测试集共 ${n0(test.test_set.rows)} 行、${n0(test.test_set.customers)} 名客户、${test.test_set.as_of_points} 个周时点，正例比例 ${pct(test.test_set.positive_rate)}。`),
  ...figure(fig("fig_test.png"), 2000, 720, "测试集 ROC-AUC 区间与周内 Lift@10%"),
  ...table("测试集主要指标", ["指标", "逻辑回归", "规则：90 天订单数", "规则：最近购买", "基率常数"], [
    ["ROC-AUC（95% 区间）", `${p.roc_auc.toFixed(3)} [${p.roc_auc_95ci.join(", ")}]`, `${rf.roc_auc.toFixed(3)} [${rf.roc_auc_95ci.join(", ")}]`, rr.roc_auc.toFixed(3), "0.5"],
    ["PR-AUC", p.pr_auc.toFixed(4), rf.pr_auc.toFixed(4), rr.pr_auc.toFixed(4), String(br.pr_auc_equals_positive_rate)],
    ["周内 Lift@10%", p["weekly_lift@10%"].toFixed(2), rf["weekly_lift@10%"].toFixed(2), rr["weekly_lift@10%"].toFixed(2), "1.00"],
    ["Brier", p.brier.toFixed(5), "非概率", "非概率", br.brier.toFixed(5)],
  ], [2.4, 2.2, 2.2, 1.8, 1.4]),
  ...figure(fig("fig_calibration.png"), 1040, 720, "逻辑回归校准曲线（按预测概率十分位）", 4.0),
  H2("7.4 结论与使用边界"),
  rich([{ t: "这是一个诚实的负结果。", b: true }, `测试集 ROC-AUC ${p.roc_auc.toFixed(3)}，95% 区间包含 0.5；周内 Lift@10% 为 ${p["weekly_lift@10%"].toFixed(2)}，低于随机。也就是说，模型和规则都无法挑出“这周最可能复购”的客户。但模型的平均概率是可信的（ECE ${p.ece}，平均预测 ${pct(p.mean_pred)}，实际 ${pct(p.positive_rate)}）。`]),
  para("原因在数据本身：30 天内复购只占全部购买间隔的约 11%，母体内外的复购率接近，合成生成器中复购与历史行为的关系很弱。我们没有为了提高分数而更换目标、调整测试集或改用其他指标。"),
  para("据此确定使用方式：触达名单按价值、频次等可解释规则排序，并说明其效果同样接近随机；模型概率只作整体复购水平的参考；页面和 Agent 不得宣称“精准预测”“高风险识别”或“挽回效果”。误差分析与适用限制见 reports/model/error_analysis.md 和 docs/model_card.md。"),
];

const s8 = [
  H1("八、AI 模块与应用进展"),
  para("按原计划，AI 模块和可视化应用属于终期内容，目前已提前实现。下表区分已完成的部分和仍待完成的部分。"),
  ...table("AI 模块实际状态", ["模块", "已完成", "评测结果", "未完成 / 限制"], [
    ["LLM 适配层", "超时、重试、预算、脱敏、无密钥降级", "真实调用成功（DeepSeek）", "费用只是估算，未与账单核对"],
    ["知识检索", "指标、数据字典、模型卡、运营规则；回答带引用", `${rag.passed}/${rag.cases}`, "答案文字随 LLM 有波动"],
    ["查询助手", "意图解析→白名单 SQL→只读执行；越权与歧义拦截", `${nl2sql.cases} 例；可回答部分正确率 ${pct(nl2sql.answerable_accuracy, 0)}；拦截 ${nl2sql.refusal_cases_blocked}/${nl2sql.refusal_cases_total}`, "全新问法首测只有 80%–86%；不支持分组同比等"],
    ["经营周报", "SQL 生成事实→LLM 写文字→数字逐个回查", "对抗输入 25/25 拦截；盲测 10/10 拦截、0/14 误判", "人工抽查（≥5 份）待组员完成"],
    ["挽回 Agent", "画像→检索政策→预算检查→保存草稿；只能待人工审核", `${agent.passed}/${agent.cases}（含 ${agent.live_llm_cases} 个真实调用场景）`, "没有发送接口；策略偏保守"],
    ["三模块联调", "五种运行模式（在线、回放、降级等）可区分", `${integ.passed}/${integ.total}`, "—"],
  ], [1.6, 3, 2.8, 2.6]),
  para("可视化应用有五类页面：数据口径与质量、经营总览、客户生命周期与分群、复购预测、AI 工作台。每页都显示数据版本、时间范围，并注明数据完全合成。以下是浏览器中运行的真实截图。"),
  ...figure(shot("evidence/UI-05/test_results_browser.jpg"), 800, 514, "复购预测页：测试结果与使用边界", 5.6),
  ...figure(shot("evidence/UI-06/query_assistant_live.jpg"), 800, 514, "AI 工作台：查询助手（真实 LLM 调用）", 5.6),
  ...figure(shot("evidence/UI-06/agent_live.jpg"), 800, 514, "AI 工作台：挽回 Agent 生成待审草稿", 5.6),
];

const s9 = [
  H1("九、当前问题与风险"),
  ...table("问题与风险", ["#", "问题 / 风险", "影响", "当前处理"], [
    ["1", "教师尚未对合成数据和数据时效作书面答复", "数据口径可能需要调整", "按用户授权的工作假设推进；报告注明完全合成；答辩时当面说明"],
    ["2", "复购信号弱，模型个体区分接近随机", "不能用模型挑选名单", "如实报告；名单用规则排序；不报告挽回金额或 ROI"],
    ["3", "周报人工抽查未做", "AI 生成质量只有自动校验和 AI 测试", "安排组员按 eval/blind_test_plan.md 抽查至少 5 份"],
    ["4", "查询助手对全新问法的首测正确率 80%–86%", "现场提问可能答不了或要求澄清", "识别不了的条件会要求澄清，不会静默放宽；演示时以支持的问题为主"],
    ["5", "复现只在 macOS arm64 验证过", "其他组员电脑可能装不上", "终期前在 Windows 上试装一次"],
    ["6", "演示依赖网络和 LLM 服务", "现场断网或服务不可用", "无密钥或超时时自动降级为规则与模板；周报可回放已记录文本（醒目标注）；另备截图"],
    ["7", "非技术分工未定（文档、PPT、讲演、答辩）", "终期材料可能赶不及", "本周内确定分工（见第十一节）"],
  ], [0.5, 3.4, 2.6, 3.8]),
];

const s10 = [
  H1("十、未完成工作与终期排期"),
  para("终期截止日为 2026-12-22。项目内部计划在 12 月 13 日前冻结核心功能，12 月 18 日前完成文档和演练，留出余量。"),
  ...table("终期排期", ["时间", "工作", "负责", "完成标志"], [
    ["11-19 至 11-29", "中期答辩准备：PPT 演练、现场演示彩排、问答准备", "全组（讲演人待定）", "演练一次并记录"],
    ["11-30 前", "提交中期检查报告；现场答辩", "全组", "保存提交回执与答辩记录"],
    ["12-01 至 12-07", "周报人工抽查（≥5 份）；成员分工与个人贡献整理", "待分配组员", "抽查记录入库；个人贡献清单"],
    ["12-01 至 12-13", "正式课程报告六章（含环境、问题处理与总结）", "文档负责人（待定）＋技术负责人提供材料", "报告全文渲染逐页检查"],
    ["12-08 至 12-13", "在其他组员电脑上复现；按评审意见修正", "技术负责人", "复现记录"],
    ["12-13", "冻结代码、数据与模型版本，打包", "技术负责人", "打包清单与哈希"],
    ["12-14 至 12-18", "终期 PPT 与 10 分钟讲稿；全流程演练与个人问答", "全组", "演练记录；每人能回答 1–2 个本人模块问题"],
    ["12-22 前", "提交正式报告并现场答辩；记录真实结果", "全组", "提交回执"],
  ], [1.8, 4.2, 2.4, 2.4]),
];

const s11 = [
  H1("十一、团队分工"),
  para("已确定：数据处理、数仓、机器学习、AI 模块、前后端、集成、测试与部署等全部技术工作由组内一名成员负责，AI 编程助手协助实现与验证，所有 AI 产出都经过实际运行和证据记录。"),
  rich([{ t: "【待团队填写】", b: true, c: "C00000" }, "技术负责人姓名；课程文档、PPT、讲演、答辩、人工审核与行政事务的分工；孙卓同学的班级信息。以上内容不由 AI 代填。"]),
  ...table("分工表（待填写）", ["成员", "负责内容", "可展示的证据", "答辩准备的问题"], [
    ["李沁阳", "", "", ""], ["李浩畅（组长）", "", "", ""], ["黄思凯", "", "", ""], ["李仕仁", "", "", ""], ["孙卓", "", "", ""],
  ], [2, 3, 3, 3]),
];

const s12 = [
  H1("附录 A  复现与演示命令"),
  para("在项目目录 retail_ai_execution_kit/ 下执行（详见 docs/runbook.md）："),
  ...[
    "uv venv --python 3.12 .venv",
    "uv pip sync --python .venv/bin/python requirements.lock",
    ".venv/bin/python src/retail_bi/pipeline.py build          # 一键重建数仓",
    ".venv/bin/python src/retail_bi/warehouse/release.py publish  # 只读发布",
    ".venv/bin/python tests/release/run_regression.py          # 关键路径回归",
    ".venv/bin/streamlit run app.py --server.port 8599          # 启动应用",
  ].map((c) => new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: c, font: { ascii: "Menlo", hAnsi: "Menlo", eastAsia: "宋体" }, size: 18 })] })),
  H1("附录 B  证据索引"),
  para("报告中的每个结论都能在 reports/submission/evidence_index.md 中找到对应的代码、运行命令、结果文件和证据记录；证据记录用 SHA-256 绑定输入和产物，运行 python3 scripts/project.py validate 可核对文件是否被改动。"),
];

const doc = new Document({
  creator: "信管4班5组",
  title: "智能决策综合实践中期检查报告",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HFONT, size: 30, bold: true }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HFONT, size: 26, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18 })] })] }) },
    children: [...cover, ...toc, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9, ...s10, ...s11, ...s12],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outFile, buf);
  console.log("wrote", outFile, buf.length, "bytes;", figNo, "figures,", tabNo, "tables; tasks done", nDone, "/", nSel, "; regression", regPassed, "/", regTotal);
});
