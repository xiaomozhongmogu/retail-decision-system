# 电商零售智能决策系统：快速上手

## 这个系统是做什么的

我们用一份**合成的电商订单数据**（不是真实企业数据），搭了一套完整的分析流程：

**原始数据 → 清洗 → 分层数仓 → 客户分群 → 预测“未来 30 天会不会再买” → AI 辅助分析**，最后用一个网页把结果展示出来。

网页共有 5 页：

| 页面 | 能看什么 |
|---|---|
| 数据口径与质量 | 数据从哪来、有多少、清洗掉了什么、指标怎么算 |
| 经营总览 | 销售趋势，按品类和地区切片对比 |
| 生命周期与分群 | 客户处在哪个阶段、价值高低、流失风险 |
| 复购预测 | 模型怎么选的、测试效果、高风险客户名单 |
| AI 工作台 | 用中文提问查数、自动生成经营周报、生成挽回客户的营销草稿 |

## 怎么在自己电脑上跑起来

> 目前只在 **Apple 芯片的 Mac** 上验证过。Windows 和 Intel Mac 没有测过，命令可能需要改。

**准备**：安装 [Homebrew](https://brew.sh)，然后运行 `brew install uv libomp`。

```bash
git clone https://github.com/xiaomozhongmogu/retail-decision-system.git
cd retail-decision-system/retail_ai_execution_kit

# 1. 安装环境（只需一次，uv 会自动下载 Python 3.12）
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock

# 2. 用仓库里自带的原始数据构建数仓，并发布（约 1 分钟）
.venv/bin/python src/retail_bi/pipeline.py build
.venv/bin/python src/retail_bi/warehouse/release.py publish

# 3. 启动网页
.venv/bin/streamlit run app.py --server.port 8599
```

浏览器打开 <http://localhost:8599>，用左侧栏切换页面。如果第一次启动时终端要求输入邮箱，直接按回车跳过即可。

模型已经训练好并提交到仓库里，**不需要自己重新训练**。

## AI 功能（可选）

不配置也能用：AI 页面会改用规则和模板，并在页面上注明。
如果想接入真实大模型，把 `.env.example` 复制成 `.env`，填入 API 密钥，并另起一行加上 `LLM_ALLOW_PAID=1`（不加这一行就不会发起付费调用）。**`.env` 不要提交到仓库。**

## 常见问题

- **页面提示“尚无已发布的数据版本”**：第 2 步没跑完，重新运行 `build` 和 `publish`。
- **`import lightgbm` 报错**：缺少 `libomp`，运行 `brew install libomp`。
- **运行后 `git status` 显示几份报告被改了**：这是正常的，你本机重建时会重新生成这些记录，不用提交。
- **全量检查里有 1 项“工程导入层文件与登记一致”失败**：这是已知差异，原因是换了电脑、路径不同，数据本身没有问题。

## 想深入了解

- 完整操作手册（含训练、回归检查）：`retail_ai_execution_kit/docs/runbook.md`
- 中期报告与答辩材料：`retail_ai_execution_kit/deliverables/`
